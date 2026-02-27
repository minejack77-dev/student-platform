from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Subject(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Topic(models.Model):
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="topics",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(
                fields=["subject", "title"],
                name="uq_topic_subject_title",
            )
        ]

    def __str__(self) -> str:
        return f"{self.subject.name} | {self.title}"


class Question(models.Model):
    # оставляем только multiple choice
    class QuestionType(models.TextChoices):
        SINGLE_CHOICE = "single_choice", "Single choice"
        MULTIPLE_CHOICE = "multiple_choice", "Multiple choice"

    topic = models.ForeignKey(
        "Topic", on_delete=models.CASCADE, related_name="questions"
    )
    text = models.TextField()

    question_type = models.CharField(
        max_length=30,
        choices=QuestionType.choices,
        default=QuestionType.MULTIPLE_CHOICE,
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # В админке Question может сохраняться до вариантов — поэтому
        # строгую проверку "есть варианты" лучше делать не здесь, а
        # отдельной кнопкой/валидацией в админке или при публикации.
        super().clean()

    def __str__(self) -> str:
        return f"[{self.topic.title}] {self.text[:60]}"


class Choice(models.Model):
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="choices"
    )
    text = models.CharField(max_length=300)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.text


class Attempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        ABANDONED = "abandoned", "Abandoned"

    student = models.ForeignKey(
        "accounts.Student",
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name="attempts")

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS
    )

    def correct_count(self):
        return self.attempt_questions.filter(answer__is_correct=True).aggregate(
            models.Count("id")
        )["id__count"]

    class Meta:
        indexes = [
            models.Index(fields=["student", "started_at"]),
            models.Index(fields=["topic", "started_at"]),
        ]
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return (
            f"Attempt #{self.pk} | {self.student.user.username} | "
            f"{self.topic.title} | {self.status}"
        )


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

    # выбранные студентом варианты (может быть несколько)
    selected_choices = models.ManyToManyField(
        "Choice", blank=True, related_name="answers"
    )

    answered_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    # null = ещё не проверено (на старте можно заполнять автоматически)
    is_correct = models.BooleanField(null=True, blank=True)

    teacher_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["attempt_question__order"]

    def __str__(self) -> str:
        return f"Answer for Attempt #{self.attempt_question.attempt_id} Q{self.attempt_question.order}"

    def check_answer(self):
        correct = set(
            self.attempt_question.question.choices.filter(is_correct=True).values_list(
                "id", flat=True
            )
        )
        choises = set(
            self.attempt_question.question.choices.values_list("id", flat=True)
        )
        print("==", choises, correct)
        if choises == correct:
            self.is_correct = True
        else:
            self.is_correct = False
        self.save()
        return self.is_correct


class Group(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    teacher = models.ForeignKey(
        "accounts.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teaching_groups",
    )

    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    students = models.ManyToManyField(
        "accounts.Student",
        through="GroupStudent",
        related_name="groups",
        blank=True,
    )

    def __str__(self):
        return self.name


class GroupTeachingAssignment(models.Model):
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="teaching_assignments",
    )
    teacher = models.ForeignKey(
        "accounts.Teacher",
        on_delete=models.CASCADE,
        related_name="group_assignments",
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="teaching_assignments",
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="teaching_assignments",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "teacher"],
                name="uq_group_teacher_assignment",
            )
        ]
        ordering = ["group__name", "teacher__user__username"]

    def clean(self):
        super().clean()
        if self.topic_id and self.topic.subject_id != self.subject_id:
            raise ValidationError(
                {"topic": "Topic must belong to the selected subject."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"{self.group.name} | {self.teacher.user.username} | "
            f"{self.subject.name} | {self.topic.title if self.topic else 'No topic'}"
        )


class GroupStudent(models.Model):
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="group_students",
    )
    student = models.ForeignKey(
        "accounts.Student",
        on_delete=models.CASCADE,
        related_name="group_memberships",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "student"], name="uq_group_student"
            )
        ]

    def __str__(self) -> str:
        return f"{self.group.name} | {self.student.user.username}"


@receiver(post_save, sender=Attempt)
def complte_attempt(sender, instance, created, **kwargs):
    if instance.status == "completed":
        for q in instance.attempt_questions.all():
            q.answer.check_answer()
