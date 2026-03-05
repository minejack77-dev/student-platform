from django.db import transaction
from rest_framework import serializers

from accounts.models import Student, Teacher, User
from learning.models import Group, Topic


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
