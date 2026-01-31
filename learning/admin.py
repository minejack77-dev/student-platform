from django.contrib import admin

from .models import Topic, Question, Attempt, AttemptQuestion, Answer


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "topic", "question_type", "is_active", "created_at")
    list_filter = ("topic", "question_type", "is_active")
    search_fields = ("text",)
    autocomplete_fields = ("topic",)


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
    list_filter = ("status", "topic")
    search_fields = ("student__username", "student__email")
    autocomplete_fields = ("student", "topic")
    inlines = (AttemptQuestionInline,)


@admin.register(AttemptQuestion)
class AttemptQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "attempt", "order", "question")
    list_filter = ("attempt__topic",)
    autocomplete_fields = ("attempt", "question")
    ordering = ("attempt", "order")

    search_fields = (
        "attempt__student__username",
        "attempt__student__email",
        "attempt__topic__title",
        "question__text",
    )

    inlines = (AnswerInline,)


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "attempt_question", "is_correct", "answered_at")
    list_filter = ("is_correct", "attempt_question__attempt__topic")
    search_fields = ("answer_text", "teacher_comment")
    autocomplete_fields = ("attempt_question",)