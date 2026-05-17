from dataclasses import dataclass
from html import escape
from pathlib import Path
import re
from xml.etree import ElementTree
from zipfile import ZipFile

from django.core.exceptions import ValidationError
from django.db import transaction

from learning.models import Choice, Question


@dataclass(frozen=True)
class SpreadsheetCell:
    plain: str
    html: str


def _stringify_spreadsheet_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _is_bold_font(font) -> bool:
    return bool(getattr(font, "bold", 0) or getattr(font, "weight", 0) >= 700)


def _render_rich_text_html(*, plain_text, runlist, workbook) -> str:
    if not plain_text:
        return ""

    parts = []
    for index, (start, font_index) in enumerate(runlist):
        end = runlist[index + 1][0] if index + 1 < len(runlist) else len(plain_text)
        fragment = escape(plain_text[start:end])
        if _is_bold_font(workbook.font_list[font_index]):
            parts.append(f"<strong>{fragment}</strong>")
        else:
            parts.append(fragment)
    return "".join(parts)


def _build_cell(sheet, workbook, row_index, col_index) -> SpreadsheetCell:
    plain_text = _stringify_spreadsheet_cell(sheet.cell_value(row_index, col_index))
    if not plain_text:
        return SpreadsheetCell(plain="", html="")

    runlist = sheet.rich_text_runlist_map.get((row_index, col_index))
    if runlist:
        return SpreadsheetCell(
            plain=plain_text,
            html=_render_rich_text_html(
                plain_text=plain_text,
                runlist=runlist,
                workbook=workbook,
            ),
        )

    xf = workbook.xf_list[sheet.cell_xf_index(row_index, col_index)]
    font = workbook.font_list[xf.font_index]
    html = escape(plain_text)
    if _is_bold_font(font):
        html = f"<strong>{html}</strong>"

    return SpreadsheetCell(plain=plain_text, html=html)


def _read_spreadsheet_rows(src) -> list[list[SpreadsheetCell]]:
    src_path = Path(getattr(src, "path", src))
    if not src_path.exists():
        raise ValidationError({"src": f"Source file '{src_path}' does not exist."})
    suffix = src_path.suffix.lower()
    if suffix == ".xlsx":
        return _read_xlsx_rows(src_path)
    if suffix != ".xls":
        raise ValidationError({"src": "Only .xls and .xlsx files are supported."})

    try:
        import xlrd
    except ImportError as exc:
        raise ValidationError(
            {"src": "Excel import requires the 'xlrd' package to be installed."}
        ) from exc

    workbook = xlrd.open_workbook(src_path, formatting_info=True)
    sheet = workbook.sheet_by_index(0)
    rows = []

    for row_index in range(sheet.nrows):
        row = [
            _build_cell(sheet, workbook, row_index, col_index)
            for col_index in range(sheet.ncols)
        ]
        if any(cell.plain for cell in row):
            rows.append(row)

    return rows


XLSX_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _xlsx_text_runs(element) -> list[tuple[str, bool]]:
    runs = []
    rich_runs = element.findall("main:r", XLSX_NS)
    if rich_runs:
        for run in rich_runs:
            text = "".join(
                text_node.text or "" for text_node in run.findall("main:t", XLSX_NS)
            )
            if text:
                runs.append((text, run.find("main:rPr/main:b", XLSX_NS) is not None))
        return runs

    text = "".join(
        text_node.text or "" for text_node in element.findall(".//main:t", XLSX_NS)
    )
    return [(text, False)] if text else []


def _xlsx_cell_from_runs(runs) -> SpreadsheetCell:
    plain = "".join(text for text, _is_bold in runs)
    html_parts = []
    for text, is_bold in runs:
        fragment = escape(text)
        html_parts.append(f"<strong>{fragment}</strong>" if is_bold else fragment)
    return SpreadsheetCell(plain=plain.strip(), html="".join(html_parts).strip())


def _read_xlsx_shared_strings(archive) -> list[SpreadsheetCell]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []

    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        _xlsx_cell_from_runs(_xlsx_text_runs(shared_string))
        for shared_string in root.findall("main:si", XLSX_NS)
    ]


def _xlsx_column_index(cell_reference, fallback):
    if not cell_reference:
        return fallback

    match = re.match(r"([A-Z]+)", cell_reference.upper())
    if not match:
        return fallback

    index = 0
    for char in match.group(1):
        index = index * 26 + ord(char) - ord("A") + 1
    return index - 1


def _read_xlsx_cell(cell, shared_strings) -> SpreadsheetCell:
    cell_type = cell.get("t")
    if cell_type == "s":
        value_node = cell.find("main:v", XLSX_NS)
        if value_node is None or value_node.text is None:
            return SpreadsheetCell(plain="", html="")
        try:
            return shared_strings[int(value_node.text)]
        except (IndexError, ValueError):
            return SpreadsheetCell(plain="", html="")

    if cell_type == "inlineStr":
        inline = cell.find("main:is", XLSX_NS)
        if inline is None:
            return SpreadsheetCell(plain="", html="")
        return _xlsx_cell_from_runs(_xlsx_text_runs(inline))

    value_node = cell.find("main:v", XLSX_NS)
    value = _stringify_spreadsheet_cell(value_node.text if value_node is not None else "")
    html = escape(value)
    return SpreadsheetCell(plain=value, html=html)


def _read_xlsx_rows(src_path) -> list[list[SpreadsheetCell]]:
    with ZipFile(src_path) as archive:
        sheet_path = "xl/worksheets/sheet1.xml"
        if sheet_path not in archive.namelist():
            raise ValidationError({"src": "Spreadsheet must contain at least one sheet."})

        shared_strings = _read_xlsx_shared_strings(archive)
        root = ElementTree.fromstring(archive.read(sheet_path))
        rows = []

        for row_node in root.findall(".//main:sheetData/main:row", XLSX_NS):
            cells = []
            for fallback_index, cell_node in enumerate(
                row_node.findall("main:c", XLSX_NS)
            ):
                column_index = _xlsx_column_index(cell_node.get("r"), fallback_index)
                while len(cells) <= column_index:
                    cells.append(SpreadsheetCell(plain="", html=""))
                cells[column_index] = _read_xlsx_cell(cell_node, shared_strings)

            if any(cell.plain for cell in cells):
                rows.append(cells)

        return rows


def _create_choices(*, question, option_texts, answer_key, row_number):
    normalized_key = answer_key.casefold()
    choices = []
    correct_count = 0

    for index, option_text in enumerate(option_texts, start=1):
        is_correct = option_text.plain.casefold() == normalized_key
        if is_correct:
            correct_count += 1
        choices.append(
            Choice(
                question=question,
                text=option_text.html,
                is_correct=is_correct,
                order=index,
            )
        )

    if correct_count != 1:
        raise ValidationError(
            {"src": f"Row {row_number} must map the key to exactly one answer option."}
        )

    Choice.objects.bulk_create(choices)
    return choices


def import_questions_from_xls(*, task=None, topic=None, src, is_active=True):
    if task is None and topic is None:
        raise ValidationError({"task": "Task is required."})
    if task is not None:
        topic = task.topic
    rows = _read_spreadsheet_rows(src)
    if len(rows) < 2:
        raise ValidationError(
            {"src": "Spreadsheet must contain a header and at least one question row."}
        )

    header_cell = rows[0][0]
    if not header_cell.plain:
        raise ValidationError(
            {"src": "The first column header must contain question text."}
        )

    questions = []
    with transaction.atomic():
        for row_number, row in enumerate(rows[1:], start=2):
            if len(row) < 3:
                raise ValidationError(
                    {
                        "src": f"Row {row_number} must contain question text, options, and key."
                    }
                )

            question_cell = row[0]
            if not question_cell.plain:
                continue

            answer_key = row[-1].plain
            option_texts = [value for value in row[1:-1] if value.plain]
            if len(option_texts) < 2:
                raise ValidationError(
                    {
                        "src": f"Row {row_number} must contain at least two answer options."
                    }
                )
            if not answer_key:
                raise ValidationError(
                    {"src": f"Row {row_number} must contain an answer key."}
                )

            question_text = question_cell.html
            if header_cell.html:
                question_text = f"{header_cell.html}\n{question_text}"

            question = Question.objects.create(
                topic=topic,
                task=task,
                instruction="",
                text=question_text,
                question_type=Question.QuestionType.SINGLE_CHOICE,
                is_active=is_active,
            )
            _create_choices(
                question=question,
                option_texts=option_texts,
                answer_key=answer_key,
                row_number=row_number,
            )
            questions.append(question)

    return questions
