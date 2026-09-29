from accounts.models import Student, Teacher, User
from django.db.models import Q
from rest_framework.permissions import BasePermission, DjangoModelPermissions, SAFE_METHODS


def has_teacher_profile(user):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return user.role == User.Role.TEACHER and Teacher.objects.filter(user_id=user.pk).exists()


def has_student_profile(user):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return Student.objects.filter(user_id=user.pk).exists()


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


def can_manage_group(user, group):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    return user.is_superuser or (
        has_teacher_profile(user) and group.teacher_id is not None
        and Teacher.objects.filter(pk=group.teacher_id, user=user).exists()
    )


def visible_groups(queryset, user, *, include_student=False):
    if not user or not user.is_authenticated or not user.is_active:
        return queryset.none()
    if user.is_superuser:
        return queryset
    scope = Q(pk__in=[])
    if has_teacher_profile(user):
        scope |= Q(teacher__user=user) | Q(teaching_assignments__teacher__user=user)
    if include_student:
        scope |= Q(students__user=user)
    return queryset.filter(scope).distinct()


class GroupAccessPermission(TeacherModelPermissions):
    owner_actions = {"update", "partial_update", "destroy", "search_students", "find_student", "add_student", "remove_student"}

    def has_permission(self, request, view):
        if view.action in {"add_student", "remove_student", "teacher_assignment", "topic_calendar"} and request.method not in SAFE_METHODS:
            return has_teacher_profile(request.user) and request.user.has_perm("learning.change_group")
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if view.action in self.owner_actions:
            return can_manage_group(request.user, obj)
        return True  # The queryset already limits reads to owners/assigned teachers.


class OwnedMaterialPermissions(TeacherModelPermissions):
    def has_permission(self, request, view):
        if not has_teacher_profile(request.user):
            return False
        action_permissions = {
            "import_questions": ("learning.change_task", "learning.add_question"),
            "undo_import": ("learning.change_task", "learning.delete_question"),
            "upload_images": ("learning.change_question",),
            "delete_image": ("learning.change_question",),
        }
        if view.action in action_permissions:
            return request.user.has_perms(action_permissions[view.action])
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        from learning.services.material_access import can_edit_material
        return request.method in SAFE_METHODS or can_edit_material(request.user, obj)

def teacher_attempt_scope(user, prefix=""):
    """Owners see group results; assigned teachers see their own schedules."""
    return Q(**{f"{prefix}schedule_entry__group__teacher__user": user}) | (
        Q(**{f"{prefix}schedule_entry__teacher__user": user})
        & Q(**{f"{prefix}schedule_entry__group__teaching_assignments__teacher__user": user})
    )


class AttemptAccessPermission(BasePermission):
    """Teachers may inspect assigned attempts, but never change student work."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "role", None) == "teacher":
            return request.method in SAFE_METHODS and has_teacher_profile(request.user)
        return has_student_profile(request.user)
