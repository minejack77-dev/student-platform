from dataclasses import dataclass
from html import escape
from pathlib import Path

import re
from xml.etree import ElementTree
from zipfile import ZipFile

from django.core.exceptions import ValidationError
from django.db import transaction

from learning.models import Choice, MatchingPair, Question


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
        html = _render_rich_text_html(
            plain_text=plain_text,
            runlist=runlist,
            workbook=workbook,
        )
        return SpreadsheetCell(plain=plain_text, html=html)

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
    value = _stringify_spreadsheet_cell(
        value_node.text if value_node is not None else ""
    )
    html = escape(value)
    return SpreadsheetCell(plain=value, html=html)


def _read_xlsx_rows(src_path) -> list[list[SpreadsheetCell]]:
    with ZipFile(src_path) as archive:
        sheet_path = "xl/worksheets/sheet1.xml"
        if sheet_path not in archive.namelist():
            raise ValidationError(
                {"src": "Spreadsheet must contain at least one sheet."}
            )

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


def _split_answer_key(answer_key):
    parts = [
        part.strip().casefold()
        for part in re.split(r"[,;\n]+", answer_key or "")
        if part.strip()
    ]
    return set(parts) if parts else {(answer_key or "").strip().casefold()}


def _create_choices(*, question, option_texts, answer_key, row_number):
    normalized_keys = _split_answer_key(answer_key)
    choices = []
    correct_count = 0

    for index, option_text in enumerate(option_texts, start=1):
        is_correct = option_text.plain.strip().casefold() in normalized_keys
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

    if (
        question.question_type == Question.QuestionType.SINGLE_CHOICE
        and correct_count != 1
    ):
        raise ValidationError(
            {"src": f"Row {row_number} must map the key to exactly one answer option."}
        )
    if (
        question.question_type == Question.QuestionType.MULTIPLE_CHOICE
        and correct_count < 1
    ):
        raise ValidationError(
            {"src": f"Row {row_number} must map the key to at least one answer option."}
        )

    Choice.objects.bulk_create(choices)
    return choices


def _create_matching_pairs(*, question, pair_cells, row_number):
    pairs = []
    for index, (left_cell, right_cell) in enumerate(pair_cells, start=1):
        if not left_cell.plain or not right_cell.plain:
            raise ValidationError(
                {
                    "src": (
                        f"Row {row_number} contains an incomplete matching pair "
                        f"at pair #{index}."
                    )
                }
            )
        pairs.append(
            MatchingPair(
                question=question,
                left_content=left_cell.html,
                right_content=right_cell.html,
                order=index,
            )
        )

    if len(pairs) < 2:
        raise ValidationError(
            {"src": f"Row {row_number} must contain at least two matching pairs."}
        )

    MatchingPair.objects.bulk_create(pairs)
    return pairs


def _last_non_empty_cell_index(row):
    for index in range(len(row) - 1, -1, -1):
        if row[index].plain:
            return index
    return None


QUESTION_TYPE_ALIASES = {
    "single_choice": Question.QuestionType.SINGLE_CHOICE,
    "single": Question.QuestionType.SINGLE_CHOICE,
    "choice": Question.QuestionType.SINGLE_CHOICE,
    "multiple_choice": Question.QuestionType.MULTIPLE_CHOICE,
    "multiple": Question.QuestionType.MULTIPLE_CHOICE,
    "matching": Question.QuestionType.MATCHING,
    "match": Question.QuestionType.MATCHING,
    "сопоставление": Question.QuestionType.MATCHING,
    "соответствие": Question.QuestionType.MATCHING,
}


LEFT_HEADERS = {"left", "left 1", "left1", "левый", "слева", "левая колонка"}
RIGHT_HEADERS = {"right", "right 1", "right1", "правый", "справа", "правая колонка"}


def _question_type_from_cell(cell):
    return QUESTION_TYPE_ALIASES.get((cell.plain or "").strip().casefold())


def _normalize_question_type(value):
    if value in (None, ""):
        return None
    normalized = QUESTION_TYPE_ALIASES.get(str(value).strip().casefold())
    if normalized is None:
        raise ValidationError(
            {"question_type": "Use one of: single_choice, multiple_choice, matching."}
        )
    return normalized


def _header_declares_matching(header_row):
    if len(header_row) < 3:
        return False
    left_header = (header_row[1].plain or "").strip().casefold()
    right_header = (header_row[2].plain or "").strip().casefold()
    return left_header in LEFT_HEADERS and right_header in RIGHT_HEADERS


def _pair_cells_from_row(row, start_index, row_number):
    non_empty_cells = [cell for cell in row[start_index:] if cell.plain]
    if len(non_empty_cells) % 2 != 0:
        raise ValidationError(
            {
                "src": (
                    f"Row {row_number} must contain matching values as left/right "
                    "cell pairs."
                )
            }
        )
    return [
        (non_empty_cells[index], non_empty_cells[index + 1])
        for index in range(0, len(non_empty_cells), 2)
    ]


def import_questions_from_xls(
    *, task=None, topic=None, src, is_active=True, question_type=None
):
    if task is None and topic is None:
        raise ValidationError({"task": "Task is required."})
    if task is not None:
        topic = task.topic
    forced_question_type = _normalize_question_type(question_type)
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
    header_is_matching = _header_declares_matching(rows[0])

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

            explicit_question_type = (
                _question_type_from_cell(row[1]) if len(row) > 1 else None
            )
            resolved_question_type = (
                forced_question_type
                or explicit_question_type
                or (
                    Question.QuestionType.MATCHING
                    if header_is_matching
                    else Question.QuestionType.SINGLE_CHOICE
                )
            )
            is_matching = (
                resolved_question_type == Question.QuestionType.MATCHING
            )

            if is_matching:
                pair_start_index = 2 if explicit_question_type and not forced_question_type else 1
                pair_cells = _pair_cells_from_row(row, pair_start_index, row_number)
                question = Question.objects.create(
                    topic=topic,
                    task=task,
                    instruction=f"{header_cell.html}",
                    text=question_cell.html,
                    question_type=Question.QuestionType.MATCHING,
                    is_active=is_active,
                )
                _create_matching_pairs(
                    question=question,
                    pair_cells=pair_cells,
                    row_number=row_number,
                )
                questions.append(question)
                continue

            choice_start_index = 2 if explicit_question_type else 1
            answer_key_index = _last_non_empty_cell_index(row)
            if answer_key_index is None or answer_key_index < choice_start_index + 1:
                raise ValidationError(
                    {
                        "src": f"Row {row_number} must contain question text, options, and key."
                    }
                )

            answer_key = row[answer_key_index].plain
            option_texts = [
                value for value in row[choice_start_index:answer_key_index] if value.plain
            ]
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
                question_text = f"{question_text}"

            question = Question.objects.create(
                topic=topic,
                task=task,
                instruction=f"{header_cell.html}",
                text=question_text,
                question_type=(
                    resolved_question_type
                    if resolved_question_type in (
                        Question.QuestionType.SINGLE_CHOICE,
                        Question.QuestionType.MULTIPLE_CHOICE,
                    )
                    else Question.QuestionType.SINGLE_CHOICE
                ),
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
