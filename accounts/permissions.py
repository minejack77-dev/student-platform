from rest_framework.permissions import BasePermission


class IsAccountAdministrator(BasePermission):
    """Account administration is reserved for active superusers.

    Staff status only permits entering Django Admin; it is not authority to
    reset another user's password or create a privileged profile.
    """

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_superuser)
