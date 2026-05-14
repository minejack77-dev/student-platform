from datetime import timedelta

from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django.utils import timezone
from django_filters import FilterSet, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from accounts.models import Student, Teacher
from learning.models import (
    Group,
    GroupTopicSchedule,
    GroupTeachingAssignment,
    Question,
    Subject,
    Topic,
    Unit,
    Workbook,
    Attempt,
    AttemptQuestion,
    Answer,
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
    StudentBriefSerializer,
    SubjectSerializer,
    TopicSerializer,
    UnitSerializer,
    WorkbookSerializer,
)


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
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = SubjectSetFilter
    ordering_fields = ("name", "updated_at", "id")
    ordering = ("name",)

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


class QuestionSetFilter(FilterSet):
    topic = filters.NumberFilter(field_name="topic_id")
    text = filters.CharFilter(field_name="text", lookup_expr="icontains")
    question_type = filters.ChoiceFilter(
        field_name="question_type", choices=Question.QuestionType.choices
    )

    class Meta:
        model = Question
        fields = ("id", "topic", "text", "question_type", "is_active")


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = (
        Question.objects.select_related("topic", "topic__subject")
        .prefetch_related("choices")
        .all()
    )
    serializer_class = QuestionSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = QuestionSetFilter
    ordering = ("-created_at",)

    def _touch_topic(self, topic_id):
        Topic.objects.filter(id=topic_id).update(updated_at=timezone.now())

    def perform_create(self, serializer):
        question = serializer.save()
        self._touch_topic(question.topic_id)

    def perform_update(self, serializer):
        question = serializer.save()
        self._touch_topic(question.topic_id)

    def perform_destroy(self, instance):
        topic_id = instance.topic_id
        instance.delete()
        self._touch_topic(topic_id)


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
    queryset = (
        Group.objects.select_related("teacher__user")
        .prefetch_related(
            "students__user",
            "teaching_assignments__subject",
            "teaching_assignments__topic",
            "teaching_assignments__teacher__user",
        )
        .all()
    )
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = GroupSetFilter
    ordering_fields = ("name", "updated_at", "id")
    ordering = ("name",)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return GroupDetailSerializer
        return GroupSerializer

    def _touch_group(self, group_id):
        Group.objects.filter(id=group_id).update(updated_at=timezone.now())

    def _get_teacher_assignment(self, group, teacher):
        return (
            GroupTeachingAssignment.objects.select_related(
                "group", "teacher__user", "subject", "topic"
            )
            .filter(group=group, teacher=teacher)
            .first()
        )

    def _delete_topic_schedule(self, group, teacher, *, exclude_subject_id=None):
        queryset = GroupTopicSchedule.objects.filter(group=group, teacher=teacher)
        if exclude_subject_id is not None:
            queryset = queryset.exclude(topic__subject_id=exclude_subject_id)
        deleted_count, _details = queryset.delete()
        if deleted_count:
            self._touch_group(group.id)
        return deleted_count

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
            "topic": None,
            "topic_title": None,
            "updated_at": None,
        }

    @action(
        detail=True,
        methods=["get", "patch", "put", "delete"],
        url_path="teacher-assignment",
    )
    def teacher_assignment(self, request, pk=None):
        teacher = get_request_teacher(request)
        if not teacher:
            return Response(
                {"detail": "Only teachers can manage assignments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        group = self.get_object()
        assignment = self._get_teacher_assignment(group, teacher)

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
                        "topic": None,
                        "topic_title": None,
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
        topic = write_serializer.validated_data.get(
            "topic",
            getattr(assignment, "topic", None),
        )

        if subject is None and topic is None:
            try:
                if assignment:
                    assignment.delete()
                self._delete_topic_schedule(group, teacher)
            except ProtectedError:
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
                    "topic": None,
                    "topic_title": None,
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
                topic=topic,
            )
            created = True
        else:
            assignment.subject = subject
            assignment.topic = topic
        assignment.save()
        try:
            self._delete_topic_schedule(group, teacher, exclude_subject_id=assignment.subject_id)
        except ProtectedError:
            return Response(
                {
                    "detail": (
                        "This subject change would remove schedule dates that already have student attempts."
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
        teacher = get_request_teacher(request)
        if not teacher:
            return Response(
                {"detail": "Only teachers can manage group schedules."},
                status=status.HTTP_403_FORBIDDEN,
            )

        group = self.get_object()
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
                    "topic__subject",
                )
                .filter(
                    group=group,
                    teacher=teacher,
                    scheduled_for__range=(start_date, end_date),
                )
                .order_by("scheduled_for")
            )
            entries_by_date = {
                entry.scheduled_for: entry for entry in schedule_entries
            }

            results = []
            for index in range(days):
                current_date = start_date + timedelta(days=index)
                entry = entries_by_date.get(current_date)
                if entry is None:
                    results.append(
                        self._build_empty_topic_schedule_item(
                            group,
                            teacher,
                            current_date,
                            assignment=assignment,
                        )
                    )
                else:
                    results.append(GroupTopicScheduleSerializer(entry).data)

            return Response(
                {
                    "group": group.id,
                    "group_name": group.name,
                    "teacher": teacher.id,
                    "teacher_username": teacher.user.username,
                    "assignment_subject": assignment.subject_id if assignment else None,
                    "assignment_subject_name": assignment.subject.name if assignment else None,
                    "start_date": start_date,
                    "days": days,
                    "results": results,
                },
                status=status.HTTP_200_OK,
            )

        if request.method == "DELETE":
            date_param = request.query_params.get("date") or request.data.get("date")
            scheduled_for = parse_date(date_param) if date_param else None
            if scheduled_for is None:
                return Response(
                    {"detail": "Date is required in query parameter or request body."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                deleted_count, _details = GroupTopicSchedule.objects.filter(
                    group=group,
                    teacher=teacher,
                    scheduled_for=scheduled_for,
                ).delete()
            except ProtectedError:
                return Response(
                    {
                        "detail": (
                            "This schedule already has student attempts and cannot be removed."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if deleted_count:
                self._touch_group(group.id)
            return Response(status=status.HTTP_204_NO_CONTENT)

        write_serializer = GroupTopicScheduleWriteSerializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)

        scheduled_for = write_serializer.validated_data["date"]
        topic = write_serializer.validated_data["topic"]

        if topic is None:
            try:
                deleted_count, _details = GroupTopicSchedule.objects.filter(
                    group=group,
                    teacher=teacher,
                    scheduled_for=scheduled_for,
                ).delete()
            except ProtectedError:
                return Response(
                    {
                        "detail": (
                            "This schedule already has student attempts and cannot be removed."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
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
                        "Save a subject in this group before assigning topics to dates."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if topic.subject_id != assignment.subject_id:
            return Response(
                {"topic": "Topic must belong to your saved subject for this group."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        schedule_entry, created = GroupTopicSchedule.objects.update_or_create(
            group=group,
            teacher=teacher,
            scheduled_for=scheduled_for,
            defaults={"topic": topic},
        )
        self._touch_group(group.id)

        return Response(
            GroupTopicScheduleSerializer(schedule_entry).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="search-students")
    def search_students(self, request, pk=None):
        query = (request.query_params.get("q") or "").strip()
        if not query:
            return Response([], status=status.HTTP_200_OK)

        group = self.get_object()
        students_qs = Student.objects.select_related("user")

        if query.isdigit():
            students_qs = students_qs.filter(
                Q(user_id=int(query)) | Q(user__username__icontains=query)
            )
        else:
            students_qs = students_qs.filter(user__username__icontains=query)

        students = list(students_qs.order_by("user__username")[:20])
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

        request_student = get_request_student(request)
        request_teacher = get_request_teacher(request)

        if request_student:
            if not group.students.filter(id=request_student.id).exists():
                return Response(
                    {"detail": "You are not a member of this group."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif request_teacher:
            if not GroupTeachingAssignment.objects.filter(
                group=group, teacher=request_teacher
            ).exists():
                return Response(
                    {"detail": "You are not assigned to this group."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            return Response(status=status.HTTP_403_FORBIDDEN)

        students = group.students.select_related("user").all()
        # Запланированные тесты
        schedule_entries = GroupTopicSchedule.objects.filter(
            group=group,
            topic__is_active=True,
            topic__subject__is_active=True,
        )
        today = timezone.localdate()
        past_entries = schedule_entries.filter(scheduled_for__lte=today)

        # Все завершенные попытки с тестом
        attempts = (
            Attempt.objects.filter(
                student__in=students,
                schedule_entry__in=past_entries,
                status=Attempt.Status.COMPLETED,
            )
            .select_related("student", "schedule_entry")
        )

        #attempts_by_student = {} # Попытки каждого студента
        #for attempt in attempts:
        #   attempts_by_student.setdefault(attempt.student_id, []).append(attempt)

        #past_entry_ids = set(past_entries.values_list("id", flat=True))
        #total_past = len(past_entry_ids)
        total_past = past_entries.count()

        last_group_entry = past_entries.order_by("-scheduled_for").first()

        # attempts_by_student_entry = {}
        #for attempt in attempts:
        #    attempts_by_student_entry[(attempt.student_id, attempt.schedule_entry_id)] = attempt

        rows = []
        for student in students:
            #student_attempts = attempts_by_student.get(student.id, [])
            student_attempts = attempts.filter(student=student)
            completed = student_attempts.count()
            missed = total_past - completed
            # Количество успешных тестов
            passed = sum(1 for a in student_attempts if a.is_successful())
            # Сумма правильных ответов по всем тестам студента
            total_correct = sum(a.correct_count() for a in student_attempts)
            pass_rate = passed / total_past if total_past > 0 else 0
            if last_group_entry:
                last_attempt = attempts.filter(student=student,schedule_entry=last_group_entry)
            else:
                last_attempt = None
            #last_attempt = (
            #    attempts_by_student_entry.get((student.id, last_group_entry.id))
            #    if last_group_entry
            #    else None
            #)
            rows.append({
                "student_id": student.id,
                "username": student.user.username,
                "completed": completed,
                "missed": missed,
                "passed": passed,
                "total_correct": total_correct,
                "pass_rate": round(pass_rate * 100, 1),
                "last_correct_count": last_attempt.correct_count() if last_attempt else None,
                "last_total_questions": last_attempt.total_questions() if last_attempt else None,
                "last_result": (
                    "success" if last_attempt.is_successful() is True
                    else "fail" if last_attempt.is_successful() is False
                    else None
                ) if last_attempt else None,
            })

        # Сортируем студентов
        rows.sort(key=lambda r: (-r["pass_rate"], -r["total_correct"]))
        # Добавляем рейтинг
        for index, row in enumerate(rows, start=1):
            row["rank"] = index

        if request_student:
            # Запись с нашим студентом
            my_row = next((r for r in rows if r["student_id"] == request_student.id), None)
            return Response({
                "group_id": group.id,
                "group_name": group.name,
                "rank": my_row["rank"] if my_row else None,
                "total": len(rows),
            })

        return Response({
            "group_id": group.id,
            "group_name": group.name,
            "ranking": rows,
        })


class AttemptSetFilter(FilterSet):
    class Meta:
        model = Attempt
        fields = "__all__"


class AttemptViewSet(viewsets.ModelViewSet):
    queryset = Attempt.objects.select_related(
        "topic",
        "topic__subject",
        "student__user",
        "schedule_entry",
        "schedule_entry__group",
        "schedule_entry__teacher__user",
    )
    serializer_class = AttemptSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = AttemptSetFilter

    def get_queryset(self):
        student = get_request_student(self.request)
        if not student:
            return super().get_queryset().none()
        return super().get_queryset().filter(student=student)


class AttemptQuestionSetFilter(FilterSet):
    class Meta:
        model = AttemptQuestion
        fields = "__all__"


class AttemptQuestionViewSet(viewsets.ModelViewSet):
    queryset = AttemptQuestion.objects.select_related(
        "attempt",
        "attempt__schedule_entry",
        "question",
        "question__topic",
    ).prefetch_related(
        "question__choices",
        "answer__selected_choices",
    )
    serializer_class = AttemptQuestionSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = AttemptQuestionSetFilter

    def get_queryset(self):
        student = get_request_student(self.request)
        if not student:
            return super().get_queryset().none()
        return super().get_queryset().filter(attempt__student=student)


class AnswerSetFilter(FilterSet):
    class Meta:
        model = Answer
        fields = "__all__"


class AnswerViewSet(viewsets.ModelViewSet):
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
