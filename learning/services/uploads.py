from pathlib import Path
from django.core.exceptions import ValidationError


def validate_source_upload(value):
    # Existing files are handled by the deployment review; validate new uploads.
    if getattr(value, "_committed", False):
        return
    from learning.services.question_import import MAX_UPLOAD_BYTES, MAX_ROWS, MAX_COLUMNS, MAX_CELLS, _read_xlsx_rows
    suffix = Path(value.name).suffix.lower()
    if suffix not in {".xls", ".xlsx"} or value.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Upload an XLS/XLSX spreadsheet no larger than 8 MB.")
    try:
        value.seek(0)
        if suffix == ".xlsx":
            _read_xlsx_rows(value)
        else:
            import xlrd
            workbook = xlrd.open_workbook(file_contents=value.read(MAX_UPLOAD_BYTES + 1), on_demand=True, ragged_rows=True)
            try:
                sheet = workbook.sheet_by_index(0)
                if sheet.nrows > MAX_ROWS or sheet.ncols > MAX_COLUMNS or sheet.nrows * sheet.ncols > MAX_CELLS:
                    raise ValidationError("Spreadsheet exceeds import limits.")
            finally:
                workbook.release_resources()
    except ValidationError:
        raise
    except Exception:
        raise ValidationError("Invalid spreadsheet file.")
    finally:
        value.seek(0)
