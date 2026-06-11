import re


_NATURAL_SORT_RE = re.compile(r"(\d+)")


def natural_sort_key(value):
    parts = _NATURAL_SORT_RE.split((value or "").casefold())
    return [int(part) if part.isdigit() else part for part in parts]


def student_username_sort_key(student):
    return (natural_sort_key(student.user.username), student.id)


def sort_students_naturally(students):
    return sorted(students, key=student_username_sort_key)
