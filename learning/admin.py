from django.contrib import admin
from django import forms
from django.http import JsonResponse
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
    Unit,
    Workbook,
)


def clean_admin_id(value):
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def set_widget_attr(field, name, value):
    widget = getattr(field.widget, "widget", field.widget)
    widget.attrs[name] = value


class TopicAdminForm(forms.ModelForm):
    workbook = forms.ModelChoiceField(
        queryset=Workbook.objects.none(),
        required=False,
        label="Workbook",
    )

    class Meta:
        model = Topic
        fields = "__all__"

    class Media:
        js = ("learning/admin/topic_hierarchy_v2.js",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unit"].required = True
        set_widget_attr(
            self.fields["workbook"],
            "data-options-url",
            reverse("admin:learning_topic_workbook_options"),
        )
        set_widget_attr(
            self.fields["unit"],
            "data-options-url",
            reverse("admin:learning_topic_unit_options"),
        )

        subject_id = self._field_value("subject")
        workbook_id = self._field_value("workbook")

        if self.instance and self.instance.pk:
            subject_id = subject_id or self.instance.subject_id
            if self.instance.unit_id:
                workbook_id = workbook_id or self.instance.unit.workbook_id
                self.initial["workbook"] = self.instance.unit.workbook_id

        if subject_id:
            self.fields["workbook"].queryset = Workbook.objects.filter(
                subject_id=subject_id
            ).order_by("title")
        elif workbook_id:
            self.fields["workbook"].queryset = Workbook.objects.filter(
                id=workbook_id
            )

        if workbook_id:
            self.fields["unit"].queryset = Unit.objects.filter(
                workbook_id=workbook_id
            ).order_by("title")
        elif self.instance and self.instance.pk and self.instance.unit_id:
            self.fields["unit"].queryset = Unit.objects.filter(id=self.instance.unit_id)
        else:
            self.fields["unit"].queryset = Unit.objects.none()

    def _field_value(self, field_name):
        if not self.is_bound:
            value = self.initial.get(field_name)
            return clean_admin_id(getattr(value, "id", value))

        value = self.data.get(self.add_prefix(field_name))
        return clean_admin_id(value)

    def clean(self):
        cleaned_data = super().clean()
        subject = cleaned_data.get("subject")
        workbook = cleaned_data.get("workbook")
        unit = cleaned_data.get("unit")

        if unit:
            unit_workbook = unit.workbook
            if workbook and unit_workbook.id != workbook.id:
                self.add_error("unit", "Unit must belong to the selected workbook.")
            if subject and unit_workbook.subject_id != subject.id:
                self.add_error("unit", "Unit must belong to the selected subject.")
            cleaned_data["subject"] = unit_workbook.subject
            return cleaned_data

        if workbook:
            if subject and workbook.subject_id != subject.id:
                self.add_error(
                    "workbook",
                    "Workbook must belong to the selected subject.",
                )
            self.add_error("unit", "Select a unit for the selected workbook.")

        return cleaned_data


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Workbook)
class WorkbookAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "is_active", "updated_at")
    list_filter = ("is_active", "subject")
    search_fields = ("title", "subject__name")
    autocomplete_fields = ("subject",)


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("title", "workbook", "subject", "is_active", "updated_at")
    list_filter = ("is_active", "workbook__subject", "workbook")
    search_fields = ("title", "workbook__title", "workbook__subject__name")
    autocomplete_fields = ("workbook",)

    def subject(self, obj):
        return obj.workbook.subject


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    form = TopicAdminForm
    fields = ("subject", "workbook", "unit", "title", "description", "is_active")
    list_display = ("title", "unit", "workbook", "subject", "is_active", "updated_at")
    list_filter = ("is_active", "subject", "unit__workbook", "unit")
    search_fields = ("title", "subject__name", "unit__title", "unit__workbook__title")

    def workbook(self, obj):
        return obj.unit.workbook if obj.unit_id else None

    def get_urls(self):
        custom_urls = [
            path(
                "workbook-options/",
                self.admin_site.admin_view(self.workbook_options),
                name="learning_topic_workbook_options",
            ),
            path(
                "unit-options/",
                self.admin_site.admin_view(self.unit_options),
                name="learning_topic_unit_options",
            ),
        ]
        return custom_urls + super().get_urls()

    def workbook_options(self, request):
        subject_id = clean_admin_id(request.GET.get("subject"))
        queryset = Workbook.objects.none()
        if subject_id:
            queryset = Workbook.objects.filter(
                subject_id=subject_id,
                is_active=True,
            ).order_by("title")
        return JsonResponse(
            {
                "results": [
                    {"id": workbook.id, "text": workbook.title}
                    for workbook in queryset
                ]
            }
        )

    def unit_options(self, request):
        workbook_id = clean_admin_id(request.GET.get("workbook"))
        queryset = Unit.objects.none()
        if workbook_id:
            queryset = Unit.objects.filter(
                workbook_id=workbook_id,
                is_active=True,
            ).order_by("title")
        return JsonResponse(
            {
                "results": [
                    {"id": unit.id, "text": unit.title}
                    for unit in queryset
                ]
            }
        )


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
