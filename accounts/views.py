from datetime import timedelta

from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import ensure_csrf_cookie
from django_filters import FilterSet, filters
from rest_framework import status, viewsets
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.filters import OrderingFilter
from rest_framework.views import APIView
from rest_framework.response import Response

from accounts.models import Student, Teacher, User
from accounts.serializers import (
    AuthLoginSerializer,
    AuthUserSerializer,
    StudentSerializer,
    TeacherSerializer,
    UserSerializer,
)
from learning.models import Attempt, GroupTopicSchedule


@method_decorator(ensure_csrf_cookie, name="dispatch")
# Декоратор
# ensure_csrf_cookie если у пользователя нет CSRF, Django вернет его
# dispatch проверяет метод запроса
class CsrfCookieView(APIView):
    permission_classes = [AllowAny] # endpoint доступен всем

    def get(self, _request):
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Создаем объект сериализатора и передаем в него данные
        serializer = AuthLoginSerializer(data=request.data)
        # Запускается проверка данных
        # Если все данные правильные serializer.is_valid() вернет true
        # raise_exception=True мы ожидаем, что все поля правильные. Если нет, клиент получит 400
        # После валидации можно безопасно брать serializer.validated_data["username"] и прочее
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request=request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.is_active:
            return Response(
                {"detail": "This account is disabled."},
                status=status.HTTP_403_FORBIDDEN,
            )

        login(request, user)
        # user Django-модель
        # AuthUserSerializer(user) превращаем Python данные в удобную структуру данных, пригодную для JSON
        # .data готовое сериализованное представление пользователя
        return Response(AuthUserSerializer(user).data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(AuthUserSerializer(request.user).data, status=status.HTTP_200_OK)


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

        all_param = request.query_params.get("all", "false").lower() == "true"

        if all_param:
            # Все тесты студента
            schedule_entries = (
                GroupTopicSchedule.objects.select_related(
                    "group",
                    "teacher__user",
                    "topic",
                    "topic__subject",
                )
                .filter(
                    group__students=student,
                    group__is_active=True,
                    topic__is_active=True,
                    topic__subject__is_active=True,
                )
                .order_by("scheduled_for", "group__name", "teacher__user__username")
                .distinct()
            )
            # Попытки студента
            attempts = (
                Attempt.objects.select_related("schedule_entry")
                .filter(student=student, schedule_entry__in=schedule_entries)
                .order_by("-started_at")
            )
            attempts_by_schedule_entry_id = {}
            for attempt in attempts:
                attempts_by_schedule_entry_id.setdefault(attempt.schedule_entry_id, attempt)

            items = []
            for entry in schedule_entries:
                attempt = attempts_by_schedule_entry_id.get(entry.id)
                # Количество правильных ответов
                correct_count = attempt.correct_count() if attempt else None
                # Количество вопрос
                total_questions = attempt.total_questions() if attempt else None
                # Сдан ли тест
                success = attempt.is_successful() if attempt else None
                items.append(
                    {
                        "date": entry.scheduled_for,
                        "schedule_entry_id": entry.id,
                        "group_id": entry.group_id,
                        "group_name": entry.group.name,
                        "teacher_id": entry.teacher_id,
                        "teacher_username": entry.teacher.user.username,
                        "subject_id": entry.topic.subject_id,
                        "subject_name": entry.topic.subject.name,
                        "topic_id": entry.topic_id,
                        "topic_title": entry.topic.title,
                        "attempt_id": attempt.id if attempt else None,
                        "attempt_status": attempt.status if attempt else None,
                        "correct_count": correct_count,
                        "total_questions": total_questions,
                        "result_outcome": (
                            "success" if success is True else "fail" if success is False else None
                        ),
                    }
                )
            return Response({"student": student.id, "results": items}, status=status.HTTP_200_OK)

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
                group__students=student,
                group__is_active=True,
                topic__is_active=True,
                topic__subject__is_active=True,
                scheduled_for__range=(start_date, end_date),
            )
            .order_by("scheduled_for", "group__name", "teacher__user__username")
            .distinct()
        )
        attempts = (
            Attempt.objects.select_related("schedule_entry")
            .filter(
                student=student,
                schedule_entry__in=schedule_entries,
            )
            .order_by("-started_at")
        )
        attempts_by_schedule_entry_id = {}
        for attempt in attempts:
            attempts_by_schedule_entry_id.setdefault(attempt.schedule_entry_id, attempt)

        entries_by_date = {}
        for entry in schedule_entries:
            attempt = attempts_by_schedule_entry_id.get(entry.id)
            correct_count = attempt.correct_count() if attempt else None
            total_questions = attempt.total_questions() if attempt else None
            success = attempt.is_successful() if attempt else None
            entries_by_date.setdefault(entry.scheduled_for, []).append(
                {
                    "schedule_entry_id": entry.id,
                    "group_id": entry.group_id,
                    "group_name": entry.group.name,
                    "teacher_id": entry.teacher_id,
                    "teacher_username": entry.teacher.user.username,
                    "subject_id": entry.topic.subject_id,
                    "subject_name": entry.topic.subject.name,
                    "topic_id": entry.topic_id,
                    "topic_title": entry.topic.title,
                    "attempt_id": attempt.id if attempt else None,
                    "attempt_status": attempt.status if attempt else None,
                    "correct_count": correct_count,
                    "total_questions": total_questions,
                    "result_outcome": (
                        "success" if success is True else "fail" if success is False else None
                    ),
                }
            )

        payload = []
        for index in range(days):
            current_date = start_date + timedelta(days=index)
            payload.append(
                {
                    "date": current_date,
                    "items": entries_by_date.get(current_date, []),
                }
            )

        return Response(
            {
                "student": student.id,
                "start_date": start_date,
                "days": days,
                "results": payload,
            },
            status=status.HTTP_200_OK,
        )
