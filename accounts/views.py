from django_filters import FilterSet, filters
from rest_framework import status, viewsets
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from accounts.models import Student, Teacher, User
from accounts.serializers import StudentSerializer, TeacherSerializer, UserSerializer
from learning.models import GroupTeachingAssignment


class UserSetFilter(FilterSet):
    username = filters.CharFilter(field_name="username", lookup_expr="icontains")
    email = filters.CharFilter(field_name="email", lookup_expr="icontains")
    role = filters.ChoiceFilter(field_name="role", choices=User.Role.choices)

    class Meta:
        model = User
        fields = ("id", "username", "email", "role", "is_active")


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related("student_profile", "teacher_profile").all()
    serializer_class = UserSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = UserSetFilter
    # permission_classes = [DjangoModelPermissionsOrAnonReadOnly]


class TeacherSetFilter(FilterSet):
    username = filters.CharFilter(field_name="user__username", lookup_expr="icontains")
    topic = filters.NumberFilter(field_name="topics__id")
    group = filters.NumberFilter(field_name="teaching_groups__id")

    class Meta:
        model = Teacher
        fields = ("id", "user", "topic", "group")


class TeacherViewSet(viewsets.ModelViewSet):
    queryset = (
        Teacher.objects.select_related("user")
        .prefetch_related("topics", "teaching_groups")
        .distinct()
    )
    serializer_class = TeacherSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = TeacherSetFilter


class StudentSetFilter(FilterSet):
    username = filters.CharFilter(field_name="user__username", lookup_expr="icontains")
    group = filters.NumberFilter(field_name="groups__id")

    class Meta:
        model = Student
        fields = ("id", "user", "group")


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.select_related("user").prefetch_related("groups").distinct()
    serializer_class = StudentSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = StudentSetFilter

    @action(detail=False, methods=["get"], url_path="me-assignments")
    def me_assignments(self, request):
        user = request.user
        try:
            student = user.student_profile
        except Student.DoesNotExist:
            return Response(
                {"detail": "Only students can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        assignments = (
            GroupTeachingAssignment.objects.select_related(
                "group",
                "teacher__user",
                "subject",
                "topic",
            )
            .filter(
                group__students=student,
                group__is_active=True,
                subject__is_active=True,
                topic__isnull=False,
                topic__is_active=True,
            )
            .order_by("group__name", "teacher__user__username")
            .distinct()
        )

        payload = []
        for assignment in assignments:
            payload.append(
                {
                    "group_id": assignment.group_id,
                    "group_name": assignment.group.name,
                    "teacher_id": assignment.teacher_id,
                    "teacher_username": assignment.teacher.user.username,
                    "subject_id": assignment.subject_id,
                    "subject_name": assignment.subject.name,
                    "topic_id": assignment.topic_id,
                    "topic_title": assignment.topic.title,
                }
            )

        return Response(payload, status=status.HTTP_200_OK)
