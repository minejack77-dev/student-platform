from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


class ResourceInUse(APIException):
    status_code = 409
    default_detail = "This resource is referenced by existing records."
    default_code = "resource_in_use"


def api_exception_handler(exc, context):
    if isinstance(exc, ProtectedError):
        exc = ResourceInUse()
    elif isinstance(exc, DjangoValidationError):
        exc = ValidationError("Invalid input.")
    return exception_handler(exc, context)
