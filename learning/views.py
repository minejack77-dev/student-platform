from django.db.models import Q
from django.shortcuts import get_object_or_404
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
    GroupTeachingAssignment,
    Question,
    Subject,
    Topic,
    Attempt,
    AttemptQuestion,
    Answer,
)
from learning.serializers import (
    AnswerSerializer,
    AttemptQuestionSerializer,
    AttemptSerializer,
    GroupDetailSerializer,
    GroupSerializer,
    GroupTeachingAssignmentSerializer,
    GroupTeachingAssignmentWriteSerializer,
    QuestionSerializer,
    StudentBriefSerializer,
    SubjectSerializer,
    TopicSerializer,
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


class TopicSetFilter(FilterSet):
    title = filters.CharFilter(field_name="title", lookup_expr="icontains")
    subject = filters.NumberFilter(field_name="subject_id")

    class Meta:
        model = Topic
        fields = ("id", "title", "subject", "is_active")


class TopicViewSet(viewsets.ModelViewSet):
    queryset = Topic.objects.select_related("subject").all()
    serializer_class = TopicSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = TopicSetFilter
    ordering_fields = ("title", "updated_at", "id", "subject")
    ordering = ("title",)


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
        assignment = (
            GroupTeachingAssignment.objects.select_related(
                "group", "teacher__user", "subject", "topic"
            )
            .filter(group=group, teacher=teacher)
            .first()
        )

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
            if assignment:
                assignment.delete()
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
            if assignment:
                assignment.delete()
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
        self._touch_group(group.id)

        serializer = GroupTeachingAssignmentSerializer(assignment)
        return Response(
            serializer.data,
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


class AttemptSetFilter(FilterSet):
    class Meta:
        model = Attempt
        fields = "__all__"


class AttemptViewSet(viewsets.ModelViewSet):
    queryset = Attempt.objects.select_related("topic", "topic__subject", "student__user")
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
