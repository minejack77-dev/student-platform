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
    inlines = [TeacherInline, StudentInline]
    list_display = ("username", "email", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active")


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
