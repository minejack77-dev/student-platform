from django.db import transaction
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from copy import copy
from rest_framework import serializers

from accounts.models import Student, Teacher, User


class AuthLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class AuthUserSerializer(serializers.ModelSerializer):
    # Вычисляемые поля
    student_id = serializers.SerializerMethodField(read_only=True)
    teacher_id = serializers.SerializerMethodField(read_only=True)
    is_authenticated = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ( # Список полей которые попадут на фронт
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "student_id",
            "teacher_id",
            "is_authenticated",
        )
        read_only_fields = fields # Не редактируем поля через этот класс

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

    def get_is_authenticated(self, _obj):
        return True


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8, max_length=4096, trim_whitespace=False)
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
        if "password" in attrs:
            user = copy(self.instance) if self.instance else User()
            for name in ("username", "email", "first_name", "last_name"):
                if name in attrs:
                    setattr(user, name, attrs[name])
            try:
                validate_password(attrs["password"], user=user)
            except DjangoValidationError as error:
                raise serializers.ValidationError({"password": error.messages})
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


class ProfileSerializer(serializers.ModelSerializer):
    """Profile identity and memberships are not general-purpose CRUD fields."""

    managed_fields = ()

    def validate(self, attrs):
        errors = {
            field: "Use the dedicated management flow to change this field."
            for field in self.managed_fields
            if field in self.initial_data
        }
        user = attrs.get("user")
        if self.instance and user and user.pk != self.instance.user_id:
            errors["user"] = "The profile owner cannot be changed."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class TeacherSerializer(ProfileSerializer):
    managed_fields = ("groups", "topics")
    topics = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    group_ids = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Teacher
        fields = ("id", "user", "topics", "group_ids")
        read_only_fields = ("id", "group_ids")

    def get_group_ids(self, obj):
        return list(obj.teaching_groups.values_list("id", flat=True))

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = attrs.get("user") or (self.instance.user if self.instance else None)
        if user and user.role != User.Role.TEACHER:
            raise serializers.ValidationError({"user": "A teacher profile requires the teacher role."})
        return attrs


class StudentSerializer(ProfileSerializer):
    managed_fields = ("groups",)
    groups = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = Student
        fields = ("id", "user", "groups")
        read_only_fields = ("id",)
