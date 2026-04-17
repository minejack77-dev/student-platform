from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from learning.models import GroupStudent
from .models import Student, Teacher, User


class TeacherInline(admin.StackedInline):
    model = Teacher
    can_delete = True
    extra = 0


class StudentInline(admin.StackedInline):
    model = Student
    can_delete = True
    extra = 0


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    fieldsets = DjangoUserAdmin.fieldsets + (("Role", {"fields": ("role",)}),)
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (("Role", {"fields": ("role",)}),)

    def get_inlines(self, request, obj):
        if not obj:
            return []
        if obj.role == User.Role.TEACHER:
            return [TeacherInline]
        if obj.role == User.Role.STUDENT:
            return [StudentInline]
        return []


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("id", "user")
    search_fields = ("user__username", "user__email")


class GroupStudentInline(admin.TabularInline):
    model = GroupStudent
    extra = 1
    autocomplete_fields = ("group",)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("id", "user")
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ("user",)
    inlines = (GroupStudentInline,)
