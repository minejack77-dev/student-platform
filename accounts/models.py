from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        TEACHER = "teacher", "Teacher"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        db_index=True,
    )

    def __str__(self) -> str:
        return self.username


class Teacher(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="teacher_profile",
    )
    topics = models.ManyToManyField(
        "learning.Topic",
        related_name="teachers",
        blank=True,
    )

    def clean(self):
        if self.user.role not in (User.Role.TEACHER, User.Role.STUDENT):
            raise ValidationError({"user": "Unsupported user role for teacher profile."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.user.username


class Student(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )

    def clean(self):
        if self.user.role not in (User.Role.STUDENT, User.Role.TEACHER):
            raise ValidationError({"user": "Unsupported user role for student profile."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.user.username
