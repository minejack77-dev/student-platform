from django.contrib.auth.models import AbstractUser, Permission
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


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


TEACHER_API_MODELS = (
    "subject",
    "workbook",
    "unit",
    "topic",
    "task",
    "question",
    "group",
)


@receiver(post_save, sender=Teacher)
def grant_teacher_learning_permissions(sender, instance, **kwargs):
    user = instance.user
    if user.is_superuser:
        return

    codenames = [
        f"{action}_{model_name}"
        for model_name in TEACHER_API_MODELS
        for action in ("view", "add", "change", "delete")
    ]
    permissions = Permission.objects.filter(
        content_type__app_label="learning",
        codename__in=codenames,
    )
    user.user_permissions.add(*permissions)
