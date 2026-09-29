from django.contrib.auth.models import AbstractUser, Permission
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from webpush.models import PushInformation


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
        if self.user.role != User.Role.TEACHER:
            raise ValidationError({"user": "A teacher profile requires the teacher role."})
        if self.pk and Teacher.objects.filter(pk=self.pk).exclude(user_id=self.user_id).exists():
            raise ValidationError({"user": "The profile owner cannot be changed."})

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
        if self.pk and Student.objects.filter(pk=self.pk).exclude(user_id=self.user_id).exists():
            raise ValidationError({"user": "The profile owner cannot be changed."})

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


def teacher_learning_permissions():
    """Legacy teacher permissions, now granted explicitly by an administrator."""
    codenames = [
        f"{action}_{model_name}"
        for model_name in TEACHER_API_MODELS
        for action in ("view", "add", "change", "delete")
    ]
    return Permission.objects.filter(
        content_type__app_label="learning",
        codename__in=codenames,
    )


@receiver(post_delete, sender=Teacher)
def revoke_deleted_teacher_permissions(sender, instance, **kwargs):
    # Recreating a profile must not restore the old automatic grant.
    instance.user.user_permissions.remove(*teacher_learning_permissions())


@receiver(post_save, sender=User)
def revoke_non_teacher_permissions(sender, instance, **kwargs):
    if instance.role != User.Role.TEACHER and not kwargs.get("raw", False):
        instance.user_permissions.remove(*teacher_learning_permissions())


class PushSubscription(models.Model):
    endpoint_hash = models.CharField(max_length=64, unique=True, null=True, blank=True)
    push_information = models.OneToOneField(PushInformation, on_delete=models.CASCADE, related_name="subscription_meta")
    created_at = models.DateTimeField(auto_now_add=True)
