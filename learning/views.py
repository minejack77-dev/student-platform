from datetime import timedelta
from pathlib import Path

from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from django.db.models.deletion import ProtectedError
from rest_framework.generics import get_object_or_404
from learning.services.dates import parse_date
from django.utils import timezone
from django_filters import FilterSet, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets, serializers
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from accounts.models import Student, Teacher
from learning.models import (
    Group,
    GroupTopicSchedule,
    GroupTeachingAssignment,
    Question,
    QuestionImage,
    Subject,
    Task,
    Topic,
    Unit,
    Workbook,
    Attempt,
    AttemptQuestion,
    Answer,
)
from learning.permissions import (
    AttemptAccessPermission, GroupRankingPermission, TeacherModelPermissions,
    GroupAccessPermission, can_manage_group, visible_groups, teacher_attempt_scope,
    OwnedMaterialPermissions,
)
from learning.serializers import (
    AnswerSerializer,
    AttemptQuestionSerializer,
    AttemptSerializer,
    GroupDetailSerializer,
    GroupTopicScheduleSerializer,
    GroupTopicScheduleWriteSerializer,
    GroupSerializer,
    GroupTeachingAssignmentSerializer,
    GroupTeachingAssignmentWriteSerializer,
    QuestionSerializer,
    QuestionImageSerializer,
    StudentBriefSerializer,
    SubjectSerializer,
    TaskSerializer,
    TopicSerializer,
    UnitSerializer,
    WorkbookSerializer,
)
from learning.sorting import natural_sort_key, sort_students_naturally
from learning.services.question_import import import_questions_from_xls
from learning.services.safe_import import import_batch, undo_batch
from learning.services.attempts import submit_attempt
from learning.services.images import store_question_images


def detect_image_content_type(uploaded_file):
    header = uploaded_file.read(12)
    uploaded_file.seek(0)
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    return None


def get_request_teacher(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None
    try:
        return user.teacher_profile
    except Teacher.DoesNotExist:
        return None


def get_request_student(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None
    try:
        return user.student_profile
    except Student.DoesNotExist:
        return None


class SubjectSetFilter(FilterSet):
    name = filters.CharFilter(field_name="name", lookup_expr="icontains")

    class Meta:
        model = Subject
        fields = ("id", "name", "is_active")


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = (OwnedMaterialPermissions,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = SubjectSetFilter
    ordering_fields = ("name", "updated_at", "id")
    ordering = ("name",)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["get"], url_path="groups")
    def groups(self, request, pk=None):
        teacher = get_request_teacher(request)
        if not teacher:
            return Response(
                {"detail": "Only teachers can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        assignments = (
            GroupTeachingAssignment.objects.select_related(
                "group", "teacher__user", "subject", "topic"
            )
            .filter(teacher=teacher, subject_id=pk)
            .order_by("group__name")
        )
        serializer = GroupTeachingAssignmentSerializer(assignments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WorkbookSetFilter(FilterSet):
    title = filters.CharFilter(field_name="title", lookup_expr="icontains")
    subject = filters.NumberFilter(field_name="subject_id")

    class Meta:
        model = Workbook
        fields = ("id", "title", "subject", "is_active")


class WorkbookViewSet(viewsets.ModelViewSet):
    queryset = Workbook.objects.select_related("subject").all()
    serializer_class = WorkbookSerializer
    permission_classes = (OwnedMaterialPermissions,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = WorkbookSetFilter
    ordering_fields = ("title", "updated_at", "id", "subject")
    ordering = ("subject__name", "title")


class UnitSetFilter(FilterSet):
    title = filters.CharFilter(field_name="title", lookup_expr="icontains")
    workbook = filters.NumberFilter(field_name="workbook_id")
    subject = filters.NumberFilter(field_name="workbook__subject_id")

    class Meta:
        model = Unit
        fields = ("id", "title", "workbook", "subject", "is_active")


class UnitViewSet(viewsets.ModelViewSet):
    queryset = Unit.objects.select_related("workbook", "workbook__subject").all()
    serializer_class = UnitSerializer
    permission_classes = (OwnedMaterialPermissions,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = UnitSetFilter
    ordering_fields = ("title", "updated_at", "id", "workbook")
    ordering = ("workbook__title", "title")


class TopicSetFilter(FilterSet):
    title = filters.CharFilter(field_name="title", lookup_expr="icontains")
    subject = filters.NumberFilter(field_name="subject_id")
    workbook = filters.NumberFilter(field_name="unit__workbook_id")
    unit = filters.NumberFilter(field_name="unit_id")

    class Meta:
        model = Topic
        fields = ("id", "title", "subject", "workbook", "unit", "is_active")


class TopicViewSet(viewsets.ModelViewSet):
    queryset = Topic.objects.select_related(
        "subject",
        "unit",
        "unit__workbook",
        "unit__workbook__subject",
    ).all()
    serializer_class = TopicSerializer
    permission_classes = (OwnedMaterialPermissions,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = TopicSetFilter
    ordering_fields = (
        "title",
        "updated_at",
        "id",
        "subject",
        "unit",
        "unit__workbook",
    )
    ordering = ("unit__workbook__title", "unit__title", "title")


class TaskSetFilter(FilterSet):
    title = filters.CharFilter(field_name="title", lookup_expr="icontains")
    topic = filters.NumberFilter(field_name="topic_id")
    subject = filters.NumberFilter(field_name="topic__subject_id")

    class Meta:
        model = Task
        fields = ("id", "title", "topic", "subject", "is_active")


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.select_related("topic", "topic__subject").all()
    serializer_class = TaskSerializer
    permission_classes = (OwnedMaterialPermissions,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = TaskSetFilter
    ordering_fields = ("title", "updated_at", "id", "topic")
    ordering = ("topic__title", "title")

    @action(detail=False, methods=["post"], url_path="quick-create")
    def quick_create(self, request):
        from learning.services.materials_workflow import create_quick_task
        task = create_quick_task(request.user, request.data)
        return Response(self.get_serializer(task).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        from learning.services.materials_workflow import assign_task
        entry, created = assign_task(request.user, self.get_object(), request.data)
        return Response(GroupTopicScheduleSerializer(entry).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        url_path="import-questions",
        parser_classes=(MultiPartParser, FormParser),
    )
    def import_questions(self, request, pk=None):
        task = self.get_object()
        uploaded_file = request.FILES.get("src")
        if uploaded_file is None:
            return Response(
                {"src": "Question file is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = import_batch(task=task, upload=uploaded_file, user=request.user,
                preview=str(request.data.get("preview", "false")).lower() == "true",
                is_active=str(request.data.get("is_active", "true")).lower() not in ("false", "0", "no"),
                question_type=request.data.get("question_type") or None)
        except serializers.ValidationError:
            raise
        except Exception:
            return Response({"code": "invalid_file"}, status=status.HTTP_400_BAD_REQUEST)
        result["task"] = self.get_serializer(task).data
        return Response(result, status=status.HTTP_200_OK if result["preview"] else status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="undo-import")
    def undo_import(self, request, pk=None):
        count = undo_batch(task=self.get_object(), user=request.user, token=request.data.get("token"))
        return Response({"removed_count": count})



class QuestionSetFilter(FilterSet):
    topic = filters.NumberFilter(field_name="topic_id")
    task = filters.NumberFilter(field_name="task_id")
    text = filters.CharFilter(field_name="text", lookup_expr="icontains")
    question_type = filters.ChoiceFilter(
        field_name="question_type", choices=Question.QuestionType.choices
    )

    class Meta:
        model = Question
        fields = ("id", "topic", "task", "text", "question_type", "is_active")


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = (
        Question.objects.select_related("topic", "topic__subject")
        .prefetch_related("choices", "matching_pairs", "images")
        .all()
    )
    serializer_class = QuestionSerializer
    permission_classes = (OwnedMaterialPermissions,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = QuestionSetFilter
    ordering = ("-created_at",)

    def _touch_topic(self, topic_id):
        Topic.objects.filter(id=topic_id).update(updated_at=timezone.now())

    def _touch_task(self, task_id):
        if task_id:
            Task.objects.filter(id=task_id).update(updated_at=timezone.now())

    def perform_create(self, serializer):
        question = serializer.save()
        self._touch_topic(question.topic_id)
        self._touch_task(question.task_id)

    def perform_update(self, serializer):
        question = serializer.save()
        self._touch_topic(question.topic_id)
        self._touch_task(question.task_id)

    @transaction.atomic
    def perform_destroy(self, instance):
        topic_id = instance.topic_id
        task_id = instance.task_id
        instance.delete()
        self._touch_topic(topic_id)
        self._touch_task(task_id)

    @action(
        detail=True,
        methods=("post",),
        url_path="images",
        parser_classes=(MultiPartParser, FormParser),
    )
    def upload_images(self, request, pk=None):
        question = self.get_object()
        files = request.FILES.getlist("images")
        if not files:
            return Response(
                {"images": ["Select at least one image."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_images = store_question_images(question, files)

        self._touch_topic(question.topic_id)
        self._touch_task(question.task_id)
        return Response(
            QuestionImageSerializer(
                created_images,
                many=True,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=("delete",),
        url_path=r"images/(?P<image_id>[^/.]+)",
    )
    @transaction.atomic
    def delete_image(self, request, pk=None, image_id=None):
        question = self.get_object()
        image = get_object_or_404(question.images, pk=image_id)
        image.delete()
        self._touch_topic(question.topic_id)
        self._touch_task(question.task_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupSetFilter(FilterSet):
    title = filters.CharFilter(field_name="name", lookup_expr="icontains")
    name = filters.CharFilter(field_name="name", lookup_expr="icontains")
    teacher_subject = filters.NumberFilter(method="filter_teacher_subject")
    teacher_topic = filters.NumberFilter(method="filter_teacher_topic")

    class Meta:
        model = Group
        fields = (
            "id",
            "name",
            "teacher",
            "is_active",
            "teacher_subject",
            "teacher_topic",
        )

    def _get_teacher(self):
        request = getattr(self, "request", None)
        if not request:
            return None
        return get_request_teacher(request)

    def filter_teacher_subject(self, queryset, _name, value):
        teacher = self._get_teacher()
        if not teacher:
            return queryset.none()
        return queryset.filter(
            teaching_assignments__teacher_id=teacher.id,
            teaching_assignments__subject_id=value,
        ).distinct()

    def filter_teacher_topic(self, queryset, _name, value):
        teacher = self._get_teacher()
        if not teacher:
            return queryset.none()
        return queryset.filter(
            teaching_assignments__teacher_id=teacher.id,
            teaching_assignments__topic_id=value,
        ).distinct()


class GroupViewSet(viewsets.ModelViewSet):
    DETAILED_STATISTICS_SCALES = {
        "week": 7,
        "month": 30,
        "three_months": 90,
    }

    queryset = (
        Group.objects.select_related("teacher__user")
        .prefetch_related(
            "students__user",
            "teaching_assignments__subject",
            "teaching_assignments__workbook",
            "teaching_assignments__topic",
            "teaching_assignments__task",
            "teaching_assignments__teacher__user",
        )
        .all()
    )
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = GroupSetFilter
    ordering_fields = ("name", "updated_at", "id")
    ordering = ("name",)

    def get_permissions(self):
        if self.action == "ranking":
            return [GroupRankingPermission()]
        return [GroupAccessPermission()]

    def get_queryset(self):
        return visible_groups(super().get_queryset(), self.request.user, include_student=self.action == "ranking")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return GroupDetailSerializer
        return GroupSerializer

    def _touch_group(self, group_id):
        Group.objects.filter(id=group_id).update(updated_at=timezone.now())

    def perform_create(self, serializer):
        teacher = get_request_teacher(self.request)
        if teacher and not self.request.user.is_superuser:
            serializer.save(teacher=teacher)
        else:
            serializer.save()

    def _has_group_member_management_access(self, group):
        return can_manage_group(self.request.user, group)

    def _assignment_teacher(self, request, group):
        teacher = get_request_teacher(request)
        target = request.query_params.get("teacher") if request.method == "GET" else request.data.get("teacher")
        if target is not None:
            if not can_manage_group(request.user, group):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Only the group owner can select another teacher.")
            field = serializers.PrimaryKeyRelatedField(queryset=Teacher.objects.filter(user__is_active=True, user__role="teacher"))
            teacher = field.run_validation(target)
        if teacher is None:
            raise serializers.ValidationError({"teacher": "Select a teacher."})
        return teacher

    def _group_member_management_denied_response(self):
        return Response(
            {"detail": "You are not allowed to manage students in this group."},
            status=status.HTTP_403_FORBIDDEN,
        )

    def _get_teacher_assignment(self, group, teacher):
        return (
            GroupTeachingAssignment.objects.select_related(
                "group", "teacher__user", "subject", "workbook", "topic", "task"
            )
            .filter(group=group, teacher=teacher)
            .first()
        )

    def _delete_topic_schedule(
        self,
        group,
        teacher,
        *,
        exclude_subject_id=None,
        exclude_workbook_id=None,
    ):
        queryset = GroupTopicSchedule.objects.filter(group=group, teacher=teacher)
        valid_queryset = queryset
        if exclude_subject_id is not None:
            valid_queryset = valid_queryset.filter(topic__subject_id=exclude_subject_id)
        if exclude_workbook_id is not None:
            valid_queryset = valid_queryset.filter(
                topic__unit__workbook_id=exclude_workbook_id
            )
        if exclude_subject_id is not None or exclude_workbook_id is not None:
            queryset = queryset.exclude(id__in=valid_queryset.values("id"))
        if queryset.filter(attempts__isnull=False).exists():
            raise ProtectedError(
                "This schedule already has student attempts and cannot be removed.",
                [],
            )
        deleted_count, _details = queryset.delete()
        if deleted_count:
            self._touch_group(group.id)
        return deleted_count

    def _delete_schedule_queryset(self, queryset):
        if queryset.filter(attempts__isnull=False).exists():
            return (
                None,
                Response(
                    {
                        "detail": (
                            "This scheduled task already has student attempts in this group "
                            "and cannot be removed."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                ),
            )
        try:
            deleted_count, _details = queryset.delete()
        except ProtectedError:
            return (
                None,
                Response(
                    {
                        "detail": (
                            "This scheduled task already has student attempts in this group "
                            "and cannot be removed."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                ),
            )
        return deleted_count, None

    def _build_empty_topic_schedule_item(self, group, teacher, scheduled_for, assignment=None):
        return {
            "id": None,
            "group": group.id,
            "group_name": group.name,
            "teacher": teacher.id,
            "teacher_username": teacher.user.username,
            "date": scheduled_for,
            "subject": assignment.subject_id if assignment else None,
            "subject_name": assignment.subject.name if assignment else None,
            "workbook": assignment.workbook_id if assignment else None,
            "workbook_title": assignment.workbook.title if assignment and assignment.workbook else None,
            "topic": None,
            "topic_title": None,
            "task": None,
            "task_title": None,
            "updated_at": None,
        }

    def _resolve_detailed_statistics_window(self, request):
        scale = request.query_params.get("scale", "week")
        if scale not in self.DETAILED_STATISTICS_SCALES:
            return None, None, None, None, Response(
                {"scale": "Use one of: week, month, three_months."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        end_date_param = request.query_params.get("end_date")
        end_date = parse_date(end_date_param) if end_date_param else timezone.localdate()
        if end_date is None:
            return None, None, None, None, Response(
                {"end_date": "Enter a valid date in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if scale == "week":
            start_date = end_date - timedelta(days=end_date.weekday())
            week_end_date = start_date + timedelta(days=6)
            return scale, 7, start_date, week_end_date, None

        days = self.DETAILED_STATISTICS_SCALES[scale]
        start_date = end_date - timedelta(days=days - 1)
        return scale, days, start_date, end_date, None

    def _build_detailed_statistics_test(self, entry, attempt):
        if attempt and attempt.status == Attempt.Status.COMPLETED:
            result = "success" if attempt.is_success else "fail"
            correct_count = attempt.stats_correct_answers
            total_questions = attempt.stats_total_questions
        else:
            ready = bool(entry.task_id and entry.task.is_active and
                         entry.task.questions.filter(is_active=True).count() >= entry.task.questions_per_attempt)
            today = timezone.localdate()
            result = ("not_ready" if not ready else
                      "missed" if entry.scheduled_for < today else
                      "in_progress" if attempt else
                      "upcoming" if entry.scheduled_for > today else "not_started")
            correct_count = None
            total_questions = None

        return {
            "schedule_entry_id": entry.id,
            "task_id": entry.task_id,
            "task_title": entry.task.title if entry.task_id else None,
            "topic_title": entry.topic.title,
            "attempt_id": attempt.id if attempt else None,
            "result": result,
            "correct_count": correct_count,
            "total_questions": total_questions,
        }

    def _build_detailed_statistics_cell(self, current_date, entries, attempts_by_key, student_id):
        tests = []
        for entry in entries:
            tests.append(
                self._build_detailed_statistics_test(
                    entry,
                    attempts_by_key.get((student_id, entry.id)),
                )
            )

        if not tests:
            state = "no_test"
        elif any(test["result"] == "missed" for test in tests):
            state = "missed"
        elif any(test["result"] in ("not_ready", "not_started", "upcoming", "in_progress") for test in tests):
            state = "pending"
        elif all(test["correct_count"] == test["total_questions"] and test["total_questions"] for test in tests):
            state = "all_correct"
        elif any((test["correct_count"] or 0) > 0 for test in tests):
            state = "partial"
        else:
            state = "none_correct"

        return {
            "date": current_date.isoformat(),
            "state": state,
            "tests": tests,
        }

    def _build_group_ranking_rows(self, group, selected_date):
        schedule_entries = GroupTopicSchedule.objects.filter(
            group=group,
            topic__is_active=True,
            topic__subject__is_active=True,
        )
        current_date = timezone.localdate()
        ranking_cutoff = min(selected_date, current_date)
        past_entries = schedule_entries.filter(scheduled_for__lte=ranking_cutoff)
        selected_entries = list(
            schedule_entries.filter(scheduled_for=selected_date)
            .select_related("task", "topic")
            .order_by("scheduled_for", "id")
        )

        expired_ready_ids = [entry.id for entry in past_entries.select_related("task")
                             if entry.scheduled_for < current_date and entry.task_id and entry.task.is_active
                             and entry.task.questions.filter(is_active=True).count() >= entry.task.questions_per_attempt]
        students = Student.objects.select_related("user").filter(groups=group).annotate(
            completed=Count(
                "attempts",
                filter=Q(
                    attempts__schedule_entry__in=past_entries,
                    attempts__status=Attempt.Status.COMPLETED,
                ),
                distinct=True,
            ),
            passed=Count(
                "attempts",
                filter=Q(
                    attempts__schedule_entry__in=past_entries,
                    attempts__status=Attempt.Status.COMPLETED,
                    attempts__is_success=True,
                ),
                distinct=True,
            ),
            total_correct=Count(
                "attempts__attempt_questions",
                filter=Q(
                    attempts__schedule_entry__in=past_entries,
                    attempts__status=Attempt.Status.COMPLETED,
                    attempts__attempt_questions__answer__is_correct=True,
                ),
                distinct=True,
            ),
        )

        today_attempts = {}
        for attempt in (
            Attempt.objects.filter(
                student__in=students,
                schedule_entry__in=selected_entries,
                status=Attempt.Status.COMPLETED,
            )
            .select_related("schedule_entry", "task", "topic")
            .order_by("student_id", "schedule_entry_id", "-id")
        ):
            today_attempts.setdefault((attempt.student_id, attempt.schedule_entry_id), attempt)

        rows = []
        for student in students:
            finished_expired = Attempt.objects.filter(student=student,
                schedule_entry_id__in=expired_ready_ids, status=Attempt.Status.COMPLETED).count()
            missed = len(expired_ready_ids) - finished_expired
            total_counted = student.completed + missed
            pass_rate = student.passed / total_counted if total_counted else 0
            today_results = []
            for entry in selected_entries:
                today_attempt = today_attempts.get((student.id, entry.id))
                today_results.append({
                    "attempt_id": today_attempt.id if today_attempt else None,
                    "schedule_entry_id": entry.id,
                    "task_id": entry.task_id,
                    "task_title": entry.task.title if entry.task_id else None,
                    "topic_title": entry.topic.title,
                    "correct_count": (
                        today_attempt.correct_count() if today_attempt else None
                    ),
                    "total_questions": (
                        today_attempt.total_questions() if today_attempt else None
                    ),
                    "result": (
                        "success" if today_attempt and today_attempt.is_success is True
                        else "fail" if today_attempt and today_attempt.is_success is False
                        else None
                    ),
                })
            rows.append({
                "student_id": student.id,
                "username": student.user.username,
                "completed": student.completed,
                "missed": missed,
                "passed": student.passed,
                "total_correct": student.total_correct,
                "pass_rate": round(pass_rate * 100, 1),
                "today_results": today_results,
            })

        rows.sort(
            key=lambda row: (
                -row["pass_rate"],
                -row["total_correct"],
                natural_sort_key(row["username"]),
                row["student_id"],
            )
        )
        for index, row in enumerate(rows, start=1):
            row["rank"] = index

        return rows

    def _get_rank_trend(self, current_rank, previous_rank):
        if current_rank is None or previous_rank is None:
            return None
        if current_rank < previous_rank:
            return "up"
        if current_rank > previous_rank:
            return "down"
        return None

    @action(
        detail=True,
        methods=["get", "patch", "put", "delete"],
        url_path="teacher-assignment",
    )
    @transaction.atomic
    def teacher_assignment(self, request, pk=None):
        group = self.get_object()
        teacher = self._assignment_teacher(request, group)
        assignment = self._get_teacher_assignment(group, teacher)
        if request.method != "GET" and assignment is None and not can_manage_group(request.user, group):
            return Response({"detail": "Only the group owner can create a teaching assignment."}, status=status.HTTP_403_FORBIDDEN)

        if request.method == "GET":
            if not assignment:
                return Response(
                    {
                        "group": group.id,
                        "group_name": group.name,
                        "teacher": teacher.id,
                        "teacher_username": teacher.user.username,
                        "subject": None,
                        "subject_name": None,
                        "workbook": None,
                        "workbook_title": None,
                        "topic": None,
                        "topic_title": None,
                        "task": None,
                        "task_title": None,
                        "updated_at": None,
                    },
                    status=status.HTTP_200_OK,
                )
            serializer = GroupTeachingAssignmentSerializer(assignment)
            return Response(serializer.data, status=status.HTTP_200_OK)

        if request.method == "DELETE":
            try:
                if assignment:
                    assignment.delete()
                self._delete_topic_schedule(group, teacher)
            except ProtectedError:
                transaction.set_rollback(True)
                return Response(
                    {
                        "detail": (
                            "This schedule already has student attempts and cannot be removed."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            self._touch_group(group.id)
            return Response(status=status.HTTP_204_NO_CONTENT)

        write_serializer = GroupTeachingAssignmentWriteSerializer(
            instance=assignment,
            data=request.data,
            partial=request.method == "PATCH",
        )
        write_serializer.is_valid(raise_exception=True)

        subject = write_serializer.validated_data.get(
            "subject",
            getattr(assignment, "subject", None),
        )
        workbook = write_serializer.validated_data.get(
            "workbook",
            getattr(assignment, "workbook", None),
        )
        topic = write_serializer.validated_data.get(
            "topic",
            getattr(assignment, "topic", None),
        )
        task = write_serializer.validated_data.get(
            "task",
            getattr(assignment, "task", None),
        )

        if subject is None and workbook is None and topic is None and task is None:
            try:
                if assignment:
                    assignment.delete()
                self._delete_topic_schedule(group, teacher)
            except ProtectedError:
                transaction.set_rollback(True)
                return Response(
                    {
                        "detail": (
                            "This schedule already has student attempts and cannot be removed."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            self._touch_group(group.id)
            return Response(
                {
                    "group": group.id,
                    "group_name": group.name,
                    "teacher": teacher.id,
                    "teacher_username": teacher.user.username,
                    "subject": None,
                    "subject_name": None,
                    "workbook": None,
                    "workbook_title": None,
                    "topic": None,
                    "topic_title": None,
                    "task": None,
                    "task_title": None,
                    "updated_at": None,
                },
                status=status.HTTP_200_OK,
            )

        created = False
        if assignment is None:
            assignment = GroupTeachingAssignment(
                group=group,
                teacher=teacher,
                subject=subject,
                workbook=workbook,
                topic=topic,
                task=task,
            )
            created = True
        else:
            assignment.subject = subject
            assignment.workbook = workbook
            assignment.topic = topic
            assignment.task = task
        assignment.save()
        try:
            self._delete_topic_schedule(
                group,
                teacher,
                exclude_subject_id=assignment.subject_id,
                exclude_workbook_id=assignment.workbook_id,
            )
        except ProtectedError:
            transaction.set_rollback(True)
            return Response(
                {
                    "detail": (
                        "This subject or textbook change would remove schedule dates that already have student attempts."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        self._touch_group(group.id)

        serializer = GroupTeachingAssignmentSerializer(assignment)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["get", "patch", "delete"],
        url_path="topic-calendar",
    )
    def topic_calendar(self, request, pk=None):
        group = self.get_object()
        teacher = self._assignment_teacher(request, group)
        assignment = self._get_teacher_assignment(group, teacher)

        if request.method == "GET":
            start_date_param = request.query_params.get("start_date")
            days_param = request.query_params.get("days", "7")
            start_date = (
                parse_date(start_date_param) if start_date_param else timezone.localdate()
            )
            if start_date is None:
                return Response(
                    {"detail": "Query parameter 'start_date' must be YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                days = int(days_param)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "Query parameter 'days' must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if days < 1 or days > 21:
                return Response(
                    {"detail": "Query parameter 'days' must be between 1 and 21."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            end_date = start_date + timedelta(days=days - 1)
            schedule_entries = (
                GroupTopicSchedule.objects.select_related(
                    "group",
                    "teacher__user",
                    "topic",
                    "task",
                    "topic__subject",
                )
                .filter(
                    group=group,
                    teacher=teacher,
                    scheduled_for__range=(start_date, end_date),
                )
                .order_by("scheduled_for")
            )
            entries_by_date = {}
            for entry in schedule_entries:
                entries_by_date.setdefault(entry.scheduled_for, []).append(entry)

            results = []
            for index in range(days):
                current_date = start_date + timedelta(days=index)
                entries = entries_by_date.get(current_date, [])
                if not entries:
                    results.append(
                        self._build_empty_topic_schedule_item(
                            group,
                            teacher,
                            current_date,
                            assignment=assignment,
                        )
                    )
                else:
                    for entry in entries:
                        results.append(GroupTopicScheduleSerializer(entry).data)

            return Response(
                {
                    "group": group.id,
                    "group_name": group.name,
                    "teacher": teacher.id,
                    "teacher_username": teacher.user.username,
                    "assignment_subject": assignment.subject_id if assignment else None,
                    "assignment_subject_name": assignment.subject.name if assignment else None,
                    "assignment_workbook": assignment.workbook_id if assignment else None,
                    "assignment_workbook_title": assignment.workbook.title if assignment and assignment.workbook else None,
                    "start_date": start_date,
                    "days": days,
                    "results": results,
                },
                status=status.HTTP_200_OK,
            )

        if request.method == "DELETE":
            entry_id = (
                request.query_params.get("schedule_entry")
                or request.data.get("schedule_entry")
            )
            date_param = request.query_params.get("date") or request.data.get("date")
            scheduled_for = parse_date(date_param) if date_param else None
            if entry_id:
                entry_id = serializers.IntegerField(min_value=1, max_value=9223372036854775807).run_validation(entry_id)
                queryset = GroupTopicSchedule.objects.filter(
                    id=entry_id,
                    group=group,
                    teacher=teacher,
                )
            elif scheduled_for is not None:
                task_id = request.query_params.get("task") or request.data.get("task")
                queryset = GroupTopicSchedule.objects.filter(
                    group=group,
                    teacher=teacher,
                    scheduled_for=scheduled_for,
                )
                if task_id:
                    task_id = serializers.IntegerField(min_value=1, max_value=9223372036854775807).run_validation(task_id)
                    queryset = queryset.filter(task_id=task_id)
            else:
                return Response(
                    {"detail": "Schedule id or date is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            deleted_count, error_response = self._delete_schedule_queryset(queryset)
            if error_response is not None:
                return error_response
            if deleted_count:
                self._touch_group(group.id)
            return Response(status=status.HTTP_204_NO_CONTENT)

        write_serializer = GroupTopicScheduleWriteSerializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)

        scheduled_for = write_serializer.validated_data["date"]
        task = write_serializer.validated_data.get("task")
        topic = write_serializer.validated_data.get("topic")
        if task is not None:
            topic = task.topic

        if topic is None and task is None:
            queryset = GroupTopicSchedule.objects.filter(
                group=group,
                teacher=teacher,
                scheduled_for=scheduled_for,
            )
            deleted_count, error_response = self._delete_schedule_queryset(queryset)
            if error_response is not None:
                return error_response
            if deleted_count:
                self._touch_group(group.id)
            return Response(
                self._build_empty_topic_schedule_item(
                    group,
                    teacher,
                    scheduled_for,
                    assignment=assignment,
                ),
                status=status.HTTP_200_OK,
            )

        if assignment is None or assignment.subject_id is None:
            return Response(
                {
                    "detail": (
                        "Save a subject in this group before assigning tasks to dates."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if topic.subject_id != assignment.subject_id:
            return Response(
                {"task": "Task must belong to your saved subject for this group."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if assignment.workbook_id and topic.unit.workbook_id != assignment.workbook_id:
            return Response(
                {"task": "Task must belong to your saved textbook for this group."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task = task or Task.get_default_for_topic(topic)
        active_count = task.questions.filter(is_active=True).count()
        if not task.is_active or active_count < task.questions_per_attempt:
            return Response({"code": "task_not_ready", "active": active_count,
                             "required": task.questions_per_attempt}, status=status.HTTP_400_BAD_REQUEST)

        schedule_entry, created = GroupTopicSchedule.objects.update_or_create(
            group=group,
            teacher=teacher,
            scheduled_for=scheduled_for,
            task=task,
            defaults={"topic": topic},
        )
        self._touch_group(group.id)

        return Response(
            GroupTopicScheduleSerializer(schedule_entry).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="detailed-statistics")
    def detailed_statistics(self, request, pk=None):
        group = self.get_object()
        teacher = get_request_teacher(request)
        if not teacher and not request.user.is_superuser:
            return Response(
                {"detail": "Only teachers can view detailed statistics."},
                status=status.HTTP_403_FORBIDDEN,
            )

        scale, days, start_date, end_date, error_response = (
            self._resolve_detailed_statistics_window(request)
        )
        if error_response is not None:
            return error_response

        students = sort_students_naturally(
            Student.objects.select_related("user")
            .filter(groups=group)
        )
        ranking_by_student_id = {
            row["student_id"]: row
            for row in self._build_group_ranking_rows(group, end_date)
        }
        previous_ranking_by_student_id = {
            row["student_id"]: row["rank"]
            for row in self._build_group_ranking_rows(
                group,
                end_date - timedelta(days=1),
            )
        }
        schedules = GroupTopicSchedule.objects.select_related("task", "topic").filter(
            group=group, scheduled_for__range=(start_date, end_date),
        )
        if not can_manage_group(request.user, group):
            schedules = schedules.filter(teacher=teacher)
        schedule_entries = list(schedules.order_by("scheduled_for", "id"))

        attempts = (
            Attempt.objects.filter(
                student__in=students,
                schedule_entry__in=schedule_entries,
            )
            .select_related("schedule_entry", "task", "topic")
            .annotate(
                stats_total_questions=Count("attempt_questions", distinct=True),
                stats_correct_answers=Count(
                    "attempt_questions",
                    filter=Q(attempt_questions__answer__is_correct=True),
                    distinct=True,
                ),
            )
            .order_by("student_id", "schedule_entry_id", "-id")
        )
        attempts_by_key = {}
        for attempt in attempts:
            attempts_by_key.setdefault((attempt.student_id, attempt.schedule_entry_id), attempt)

        entries_by_date = {}
        for entry in schedule_entries:
            entries_by_date.setdefault(entry.scheduled_for, []).append(entry)

        date_columns = []
        student_rows = []
        for index in range(days):
            current_date = start_date + timedelta(days=index)
            date_columns.append(
                {
                    "date": current_date.isoformat(),
                    "scheduled_count": len(entries_by_date.get(current_date, [])),
                }
            )

        for student in students:
            cells = []
            for index in range(days):
                current_date = start_date + timedelta(days=index)
                cells.append(
                    self._build_detailed_statistics_cell(
                        current_date,
                        entries_by_date.get(current_date, []),
                        attempts_by_key,
                        student.id,
                    )
                )
            student_rows.append(
                {
                    "student_id": student.id,
                    "username": student.user.username,
                    "rank": ranking_by_student_id.get(student.id, {}).get("rank"),
                    "rank_trend": self._get_rank_trend(
                        ranking_by_student_id.get(student.id, {}).get("rank"),
                        previous_ranking_by_student_id.get(student.id),
                    ),
                    "cells": cells,
                }
            )

        return Response(
            {
                "group_id": group.id,
                "group_name": group.name,
                "scale": scale,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "dates": date_columns,
                "students": student_rows,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="search-students")
    def search_students(self, request, pk=None):
        query = (request.query_params.get("q") or "").strip()
        if not query:
            return Response([], status=status.HTTP_200_OK)

        group = self.get_object()
        if not self._has_group_member_management_access(group):
            return self._group_member_management_denied_response()
        students_qs = Student.objects.select_related("user")

        if query.isdigit():
            students_qs = students_qs.filter(
                Q(user_id=int(query)) | Q(user__username__icontains=query)
            )
        else:
            students_qs = students_qs.filter(user__username__icontains=query)

        students = sort_students_naturally(students_qs.order_by("user__username", "pk")[:100])[:20]
        in_group_student_ids = set(group.students.values_list("id", flat=True))

        payload = []
        for student in students:
            data = StudentBriefSerializer(student).data
            data["in_group"] = student.id in in_group_student_ids
            payload.append(data)

        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="find-student")
    def find_student(self, request, pk=None):
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response(
                {"detail": "Query parameter 'user_id' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        group = self.get_object()
        if not self._has_group_member_management_access(group):
            return self._group_member_management_denied_response()
        student = get_object_or_404(
            Student.objects.select_related("user"), user_id=user_id
        )
        data = StudentBriefSerializer(student).data
        data["in_group"] = group.students.filter(id=student.id).exists()
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="add-student")
    def add_student(self, request, pk=None):
        user_id = request.data.get("user_id")
        if not user_id:
            return Response(
                {"detail": "Field 'user_id' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        group = self.get_object()
        if not self._has_group_member_management_access(group):
            return self._group_member_management_denied_response()
        student = get_object_or_404(
            Student.objects.select_related("user"), user_id=user_id
        )
        is_member = group.students.filter(id=student.id).exists()
        if not is_member:
            group.students.add(student)
            self._touch_group(group.id)

        return Response(
            {
                "added": not is_member,
                "student": StudentBriefSerializer(student).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="remove-student")
    def remove_student(self, request, pk=None):
        user_id = request.data.get("user_id")
        if not user_id:
            return Response(
                {"detail": "Field 'user_id' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        group = self.get_object()
        if not self._has_group_member_management_access(group):
            return self._group_member_management_denied_response()
        student = get_object_or_404(
            Student.objects.select_related("user"), user_id=user_id
        )
        is_member = group.students.filter(id=student.id).exists()
        if is_member:
            group.students.remove(student)
            self._touch_group(group.id)

        return Response(
            {
                "removed": is_member,
                "student": StudentBriefSerializer(student).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="ranking")
    def ranking(self, request, pk=None):
        group = self.get_object()
        date_param = request.query_params.get("date")
        selected_date = parse_date(date_param) if date_param else timezone.localdate()
        if date_param and selected_date is None:
            return Response(
                {"date": "Enter a valid date in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request_student = get_request_student(request) if request.user.role == "student" and not request.user.is_superuser else None
        request_teacher = get_request_teacher(request)

        if request_student:
            if not group.students.filter(id=request_student.id).exists():
                return Response(
                    {"detail": "You are not a member of this group."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif request_teacher and not can_manage_group(request.user, group):
            if not GroupTeachingAssignment.objects.filter(
                group=group, teacher=request_teacher
            ).exists():
                return Response(
                    {"detail": "You are not assigned to this group."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif not request_teacher and not request.user.is_superuser:
            return Response(status=status.HTTP_403_FORBIDDEN)

        rows = self._build_group_ranking_rows(group, selected_date)
        previous_ranking_by_student_id = {
            row["student_id"]: row["rank"]
            for row in self._build_group_ranking_rows(
                group,
                selected_date - timedelta(days=1),
            )
        }
        for row in rows:
            row["rank_trend"] = self._get_rank_trend(
                row.get("rank"),
                previous_ranking_by_student_id.get(row["student_id"]),
            )

        if request_student:
            my_row = next((r for r in rows if r["student_id"] == request_student.id), None)
            return Response({
                "group_id": group.id,
                "group_name": group.name,
                "results_date": selected_date.isoformat(),
                "rank": my_row["rank"] if my_row else None,
                "rank_trend": my_row["rank_trend"] if my_row else None,
                "total": len(rows),
            })

        return Response({
            "group_id": group.id,
            "group_name": group.name,
            "results_date": selected_date.isoformat(),
            "ranking": rows,
        })



class AttemptSetFilter(FilterSet):
    class Meta:
        model = Attempt
        fields = "__all__"


class AttemptViewSet(viewsets.ModelViewSet):
    permission_classes = (AttemptAccessPermission,)
    http_method_names = ["get", "post", "patch", "head", "options"]
    queryset = Attempt.objects.select_related(
        "topic",
        "topic__subject",
        "task",
        "student__user",
        "schedule_entry",
        "schedule_entry__group",
        "schedule_entry__teacher__user",
    )
    serializer_class = AttemptSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = AttemptSetFilter

    def get_queryset(self):
        if self.request.user.is_superuser:
            return super().get_queryset()
        if self.request.user.role == "teacher":
            teacher = get_request_teacher(self.request)
            if not teacher:
                return super().get_queryset().none()
            return super().get_queryset().filter(
                teacher_attempt_scope(self.request.user)
            ).distinct()
        student = get_request_student(self.request)
        if not student:
            return super().get_queryset().none()
        return super().get_queryset().filter(student=student)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        attempt = submit_attempt(
            attempt_id=self.get_object().pk,
            context=self.get_serializer_context(),
            answers=request.data.get("answers"),
            confirm_unanswered=request.data.get("confirm_unanswered") is True,
        )
        return Response(self.get_serializer(attempt).data)


class AttemptQuestionSetFilter(FilterSet):
    class Meta:
        model = AttemptQuestion
        fields = ("id", "attempt", "question", "order")


class AttemptQuestionViewSet(viewsets.ModelViewSet):
    permission_classes = (AttemptAccessPermission,)
    http_method_names = ["get", "head", "options"]
    queryset = AttemptQuestion.objects.select_related(
        "attempt",
        "attempt__schedule_entry",
        "question",
        "question__topic",
    ).prefetch_related(
        "question__choices",
        "question__matching_pairs",
        "question__images",
        "answer__selected_choices",
    )
    serializer_class = AttemptQuestionSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = AttemptQuestionSetFilter

    def get_queryset(self):
        if self.request.user.is_superuser:
            return super().get_queryset()
        if self.request.user.role == "teacher":
            teacher = get_request_teacher(self.request)
            if not teacher:
                return super().get_queryset().none()
            return super().get_queryset().filter(
                teacher_attempt_scope(self.request.user, "attempt__")
            ).distinct()
        student = get_request_student(self.request)
        if not student:
            return super().get_queryset().none()
        return super().get_queryset().filter(attempt__student=student)


class AnswerSetFilter(FilterSet):
    class Meta:
        model = Answer
        fields = ("id", "attempt_question", "is_correct")


class AnswerViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    queryset = Answer.objects.select_related(
        "attempt_question",
        "attempt_question__attempt",
        "attempt_question__attempt__schedule_entry",
        "attempt_question__question",
    ).prefetch_related("selected_choices")
    serializer_class = AnswerSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = AnswerSetFilter

    def get_queryset(self):
        student = get_request_student(self.request)
        if not student:
            return super().get_queryset().none()
        return super().get_queryset().filter(attempt_question__attempt__student=student)
