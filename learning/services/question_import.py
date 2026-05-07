from dataclasses import dataclass
from html import escape
from pathlib import Path

import xlrd
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
    if src_path.suffix.lower() != ".xls":
        raise ValidationError({"src": "Only .xls files are supported."})

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


def import_questions_from_xls(*, topic, src, is_active=True):
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

            question = Question.objects.create(
                topic=topic,
                instruction="{header_cell.html}",
                text=f"{question_cell.html}",
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
