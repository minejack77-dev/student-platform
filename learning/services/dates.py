from datetime import date
from django.utils.dateparse import parse_date as django_parse_date
from rest_framework.exceptions import ValidationError


def parse_date(value):
    try:
        parsed = django_parse_date(value)
    except (TypeError, ValueError, OverflowError):
        parsed = None
    # Calendar endpoints add/subtract up to a year; reserve boundary headroom.
    if parsed is None or not date(1900, 1, 1) <= parsed <= date(9998, 12, 31):
        return None
    return parsed
