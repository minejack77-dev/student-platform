from django.conf import settings
from django.db import models


class Topic(models.Model):
    title = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class Question(models.Model):
    class QuestionType(models.TextChoices):
        TEXT = "text", "Text"
        SINGLE_CHOICE = "single_choice", "Single choice"
        MULTIPLE_CHOICE = "multiple_choice", "Multiple choice"

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    question_type = models.CharField(
        max_length=30, choices=QuestionType.choices, default=QuestionType.TEXT
    )

    # На старте пусть будет просто текст (можно хранить JSON позже)
    correct_answer = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["topic", "is_active"]),
        ]
        ordering = ["topic__title", "-created_at"]

    def __str__(self) -> str:
        return f"[{self.topic.title}] {self.text[:60]}"


class Attempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        ABANDONED = "abandoned", "Abandoned"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attempts",
        limit_choices_to={"role": "student"},
    )
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name="attempts")

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS
    )

    class Meta:
        indexes = [
            models.Index(fields=["student", "started_at"]),
            models.Index(fields=["topic", "started_at"]),
        ]
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"Attempt #{self.pk} | {self.student.username} | {self.topic.title} | {self.status}"


class AttemptQuestion(models.Model):
    attempt = models.ForeignKey(
        Attempt, on_delete=models.CASCADE, related_name="attempt_questions"
    )
    question = models.ForeignKey(
        Question, on_delete=models.PROTECT, related_name="attempt_questions"
    )
    order = models.PositiveSmallIntegerField()  # 1..10

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "order"], name="uq_attempt_order"
            ),
            models.UniqueConstraint(
                fields=["attempt", "question"], name="uq_attempt_question"
            ),
        ]
        ordering = ["order"]

    def __str__(self) -> str:
        return f"Attempt #{self.attempt_id} Q{self.order}"


class Answer(models.Model):
    attempt_question = models.OneToOneField(
        AttemptQuestion, on_delete=models.CASCADE, related_name="answer"
    )

    answer_text = models.TextField(blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    # null = ещё не проверено (если нужна ручная проверка)
    is_correct = models.BooleanField(null=True, blank=True)

    teacher_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["attempt_question__order"]

    def __str__(self) -> str:
        return f"Answer for Attempt #{self.attempt_question.attempt_id} Q{self.attempt_question.order}"
