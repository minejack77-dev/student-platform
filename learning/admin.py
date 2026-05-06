from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import path, reverse

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
from .services.question_import import import_questions_from_xls


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
    change_form_template = "admin/learning/topic/change_form.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/import-from-src/",
                self.admin_site.admin_view(self.import_from_src_view),
                name="learning_topic_import_from_src",
            )
        ]
        return custom_urls + urls

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["import_from_src_url"] = reverse(
            "admin:learning_topic_import_from_src",
            args=[object_id],
        )
        return super().change_view(request, object_id, form_url, extra_context)

    def import_from_src_view(self, request, object_id):
        topic = get_object_or_404(Topic, pk=object_id)
        change_url = reverse("admin:learning_topic_change", args=[topic.pk])

        if request.method != "POST":
            return HttpResponseRedirect(change_url)

        if not topic.src:
            self.message_user(
                request,
                "Attach a .xls file to the topic before running import.",
                level=messages.ERROR,
            )
            return HttpResponseRedirect(change_url)

        try:
            questions = import_questions_from_xls(
                topic=topic,
                src=topic.src,
                is_active=topic.is_active,
            )
        except Exception as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return HttpResponseRedirect(change_url)

        self.message_user(
            request,
            f"Imported {len(questions)} questions from {topic.src.name}.",
            level=messages.SUCCESS,
        )
        return HttpResponseRedirect(change_url)


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
