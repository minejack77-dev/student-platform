from django_filters import FilterSet, filters
from django.db import transaction
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from accounts.models import Student, Teacher, User
from learning.models import Group, GroupTeachingAssignment, Topic


class UserSetFilter(FilterSet):
    username = filters.CharFilter(field_name="username", lookup_expr="icontains")
    email = filters.CharFilter(field_name="email", lookup_expr="icontains")
    role = filters.ChoiceFilter(field_name="role", choices=User.Role.choices)

    class Meta:
        model = User
        fields = ("id", "username", "email", "role", "is_active")


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    student_id = serializers.SerializerMethodField(read_only=True)
    teacher_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "password",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "is_staff",
            "student_id",
            "teacher_id",
        )
        read_only_fields = ("id", "is_staff", "student_id", "teacher_id")

    def get_student_id(self, obj):
        try:
            return obj.student_profile.id
        except Student.DoesNotExist:
            return None

    def get_teacher_id(self, obj):
        try:
            return obj.teacher_profile.id
        except Teacher.DoesNotExist:
            return None

    def validate(self, attrs):
        if self.instance is None and "password" not in attrs:
            raise serializers.ValidationError({"password": "This field is required."})
        if self.instance and "role" in attrs and attrs["role"] != self.instance.role:
            raise serializers.ValidationError(
                {"role": "Role cannot be changed for existing users."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        if user.role == User.Role.STUDENT:
            Student.objects.create(user=user)
        else:
            Teacher.objects.create(user=user)
        return user

    @transaction.atomic
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


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


class TeacherSerializer(serializers.ModelSerializer):
    topics = serializers.PrimaryKeyRelatedField(
        queryset=Topic.objects.all(), many=True, required=False
    )
    groups = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )
    group_ids = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Teacher
        fields = ("id", "user", "topics", "groups", "group_ids")
        read_only_fields = ("id", "group_ids")

    def get_group_ids(self, obj):
        return list(obj.teaching_groups.values_list("id", flat=True))

    def validate_user(self, user):
        if user.role != User.Role.TEACHER:
            raise serializers.ValidationError("User role must be 'teacher'.")
        return user

    def _replace_groups(self, teacher, groups):
        group_ids = [group.id for group in groups]
        Group.objects.filter(teacher=teacher).exclude(id__in=group_ids).update(teacher=None)
        if group_ids:
            Group.objects.filter(id__in=group_ids).update(teacher=teacher)

    @transaction.atomic
    def create(self, validated_data):
        groups = validated_data.pop("groups", [])
        teacher = super().create(validated_data)
        self._replace_groups(teacher, groups)
        return teacher

    @transaction.atomic
    def update(self, instance, validated_data):
        groups = validated_data.pop("groups", None)
        teacher = super().update(instance, validated_data)
        if groups is not None:
            self._replace_groups(teacher, groups)
        return teacher


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


class StudentSerializer(serializers.ModelSerializer):
    groups = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = Student
        fields = ("id", "user", "groups")
        read_only_fields = ("id",)

    def validate_user(self, user):
        if user.role != User.Role.STUDENT:
            raise serializers.ValidationError("User role must be 'student'.")
        return user

    @transaction.atomic
    def create(self, validated_data):
        groups = validated_data.pop("groups", [])
        student = super().create(validated_data)
        student.groups.set(groups)
        return student

    @transaction.atomic
    def update(self, instance, validated_data):
        groups = validated_data.pop("groups", None)
        student = super().update(instance, validated_data)
        if groups is not None:
            student.groups.set(groups)
        return student


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
