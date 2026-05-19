from accounts.models import Student, Teacher
from rest_framework.permissions import BasePermission, DjangoModelPermissions


def has_teacher_profile(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    try:
        user.teacher_profile
    except Teacher.DoesNotExist:
        return False
    return True


def has_student_profile(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    try:
        user.student_profile
    except Student.DoesNotExist:
        return False
    return True


class TeacherModelPermissions(DjangoModelPermissions):
    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": [],
        "HEAD": [],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }

    def has_permission(self, request, view):
        if not has_teacher_profile(request.user):
            return False
        return super().has_permission(request, view)


class GroupRankingPermission(BasePermission):
    def has_permission(self, request, view):
        return has_teacher_profile(request.user) or has_student_profile(request.user)
