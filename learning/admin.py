from django.contrib import admin
from .models import (
    Answer,
    Attempt,
    AttemptQuestion,
    Choice,
    Group,
    GroupTeachingAssignment,
    GroupStudent,
    Question,
    Subject,
    Topic,
)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "is_active", "updated_at")
    list_filter = ("is_active", "subject")
    search_fields = ("title", "subject__name")
    autocomplete_fields = ("subject",)


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 2  # сколько пустых строк для добавления сразу
    fields = ("order", "text", "is_correct")
    ordering = ("order",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "topic", "is_active", "created_at")
    list_filter = ("topic__subject", "topic", "is_active")
    search_fields = ("text",)
    autocomplete_fields = ("topic",)
    inlines = (ChoiceInline,)


class AnswerInline(admin.StackedInline):
    model = Answer
    extra = 0
    can_delete = False


class AttemptQuestionInline(admin.TabularInline):
    model = AttemptQuestion
    extra = 0
    autocomplete_fields = ("question",)
    ordering = ("order",)


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "topic", "status", "started_at", "finished_at")
    list_filter = ("status", "topic__subject", "topic")
    search_fields = ("student__user__username", "student__user__email")
    autocomplete_fields = ("student", "topic")
    inlines = (AttemptQuestionInline,)


@admin.register(AttemptQuestion)
class AttemptQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "attempt", "order", "question")
    list_filter = ("attempt__topic__subject", "attempt__topic")
    autocomplete_fields = ("attempt", "question")
    ordering = ("attempt", "order")

    search_fields = (
        "attempt__student__user__username",
        "attempt__student__user__email",
        "attempt__topic__title",
        "question__text",
    )

    inlines = (AnswerInline,)


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "attempt_question", "is_correct", "answered_at")
    list_filter = (
        "is_correct",
        "attempt_question__attempt__topic__subject",
        "attempt_question__attempt__topic",
    )
    search_fields = ("teacher_comment", "attempt_question__question__text")
    autocomplete_fields = ("attempt_question",)


class GroupStudentInline(admin.TabularInline):
    model = GroupStudent
    extra = 1
    autocomplete_fields = ("student",)


class GroupTeachingAssignmentInline(admin.TabularInline):
    model = GroupTeachingAssignment
    extra = 0
    autocomplete_fields = ("teacher", "subject", "topic")
    fields = ("teacher", "subject", "topic", "updated_at")
    readonly_fields = ("updated_at",)


@admin.register(GroupTeachingAssignment)
class GroupTeachingAssignmentAdmin(admin.ModelAdmin):
    list_display = ("group", "teacher", "subject", "topic", "updated_at")
    list_filter = ("subject", "topic")
    search_fields = ("group__name", "teacher__user__username", "subject__name", "topic__title")
    autocomplete_fields = ("group", "teacher", "subject", "topic")


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "teacher", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    autocomplete_fields = ("teacher",)
    inlines = (GroupStudentInline, GroupTeachingAssignmentInline)
