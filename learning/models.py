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


class Workbook(models.Model):
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="workbooks",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["subject__name", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["subject", "title"],
                name="uq_workbook_subject_title",
            )
        ]

    def __str__(self) -> str:
        return f"{self.subject.name} | {self.title}"


class Unit(models.Model):
    workbook = models.ForeignKey(
        Workbook,
        on_delete=models.PROTECT,
        related_name="units",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["workbook__subject__name", "workbook__title", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["workbook", "title"],
                name="uq_unit_workbook_title",
            )
        ]

    def __str__(self) -> str:
        return f"{self.workbook.title} | {self.title}"


class Topic(models.Model):
    DEFAULT_WORKBOOK_TITLE = "General"
    DEFAULT_UNIT_TITLE = "General"

    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="topics",
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="topics",
        blank=True,
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    src = models.FileField(blank=True, null=True)

    class Meta:
        ordering = ["unit__workbook__title", "unit__title", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["unit", "title"],
                name="uq_topic_unit_title",
            )
        ]

    @classmethod
    def get_default_unit(cls, subject):
        workbook, _ = Workbook.objects.get_or_create(
            subject=subject,
            title=cls.DEFAULT_WORKBOOK_TITLE,
            defaults={
                "description": "Auto-created workbook for topics without an explicit workbook.",
            },
        )
        unit, _ = Unit.objects.get_or_create(
            workbook=workbook,
            title=cls.DEFAULT_UNIT_TITLE,
            defaults={
                "description": "Auto-created unit for topics without an explicit unit.",
            },
        )
        return unit

    def clean(self):
        super().clean()
        if self.unit_id and self.subject_id:
            unit_subject_id = self.unit.workbook.subject_id
            if unit_subject_id != self.subject_id:
                raise ValidationError(
                    {"unit": "Unit must belong to the selected subject."}
                )

    def save(self, *args, **kwargs):
        if self.unit_id and not self.subject_id:
            self.subject_id = self.unit.workbook.subject_id
        elif self.subject_id and not self.unit_id:
            self.unit = self.get_default_unit(self.subject)
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        if self.unit_id:
            return f"{self.unit.workbook.title} | {self.unit.title} | {self.title}"
        return f"{self.subject.name} | {self.title}"


class Task(models.Model):
    DEFAULT_TITLE = "Default task"

    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    src = models.FileField(blank=True, null=True)

    class Meta:
        ordering = ["topic__unit__workbook__title", "topic__unit__title", "topic__title", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["topic", "title"],
                name="uq_task_topic_title",
            )
        ]

    def __str__(self) -> str:
        return f"{self.topic.title} | {self.title}"

    @classmethod
    def get_default_for_topic(cls, topic):
        task, _ = cls.objects.get_or_create(
            topic=topic,
            title=cls.DEFAULT_TITLE,
            defaults={
                "description": topic.description,
                "is_active": topic.is_active,
                "src": topic.src,
            },
        )
        return task


class Question(models.Model):
    # оставляем только multiple choice
    class QuestionType(models.TextChoices):
        SINGLE_CHOICE = "single_choice", "Single choice"
        MULTIPLE_CHOICE = "multiple_choice", "Multiple choice"

    topic = models.ForeignKey(
        "Topic", on_delete=models.CASCADE, related_name="questions"
    )
    task = models.ForeignKey(
        "Task",
        on_delete=models.CASCADE,
        related_name="questions",
        null=True,
        blank=True,
    )
    instruction = models.TextField(blank=True)
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

    def save(self, *args, **kwargs):
        if self.topic_id and not self.task_id:
            self.task = Task.get_default_for_topic(self.topic)
        elif self.task_id and not self.topic_id:
            self.topic = self.task.topic
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        owner = self.task.title if self.task_id else self.topic.title
        return f"[{owner}] {self.text[:60]}"


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

    PASSING_CORRECT_ANSWERS = 8
    QUESTIONS_PER_ATTEMPT = 10

    student = models.ForeignKey(
        "accounts.Student",
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name="attempts")
    task = models.ForeignKey(
        Task,
        on_delete=models.PROTECT,
        related_name="attempts",
        null=True,
        blank=True,
    )
    schedule_entry = models.ForeignKey(
        "GroupTopicSchedule",
        on_delete=models.PROTECT,
        related_name="attempts",
        null=True,
        blank=True,
    )

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS
    )

    def correct_count(self):
        return self.attempt_questions.filter(answer__is_correct=True).aggregate(
            models.Count("id")
        )["id__count"]

    def total_questions(self):
        return self.attempt_questions.count()

    def is_successful(self):
        if self.status != self.Status.COMPLETED:
            return None
        return self.correct_count() >= self.PASSING_CORRECT_ANSWERS

    def is_accessible_on(self, current_date):
        if not self.schedule_entry_id:
            return True
        return self.schedule_entry.scheduled_for == current_date

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "schedule_entry"],
                condition=models.Q(schedule_entry__isnull=False),
                name="uq_attempt_student_schedule_entry",
            )
        ]
        indexes = [
            models.Index(fields=["student", "started_at"]),
            models.Index(fields=["topic", "started_at"]),
            models.Index(fields=["schedule_entry"]),
        ]
        ordering = ["-started_at"]

    def save(self, *args, **kwargs):
        if self.schedule_entry_id and not self.task_id:
            self.task = self.schedule_entry.task
        elif self.topic_id and not self.task_id:
            self.task = Task.get_default_for_topic(self.topic)
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"Attempt #{self.pk} | {self.student.user.username} | "
            f"{self.task.title if self.task_id else self.topic.title} | {self.status}"
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

    answered_at = models.DateTimeField(auto_now_add=True, null=True)

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
        selected = set(self.selected_choices.values_list("id", flat=True))
        self.is_correct = selected == correct
        self.save(update_fields=["is_correct"])
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
    task = models.ForeignKey(
        Task,
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
        if self.task_id:
            if self.task.topic.subject_id != self.subject_id:
                raise ValidationError(
                    {"task": "Task must belong to the selected subject."}
                )
            if self.topic_id and self.task.topic_id != self.topic_id:
                raise ValidationError(
                    {"task": "Task must belong to the selected topic."}
                )

    def save(self, *args, **kwargs):
        if self.task_id and not self.topic_id:
            self.topic = self.task.topic
        elif self.topic_id and not self.task_id:
            self.task = Task.get_default_for_topic(self.topic)
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"{self.group.name} | {self.teacher.user.username} | "
            f"{self.subject.name} | {self.task.title if self.task else self.topic.title if self.topic else 'No task'}"
        )


class GroupTopicSchedule(models.Model):
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="topic_schedule_entries",
    )
    teacher = models.ForeignKey(
        "accounts.Teacher",
        on_delete=models.CASCADE,
        related_name="group_topic_schedule_entries",
    )
    scheduled_for = models.DateField()
    topic = models.ForeignKey(
        Topic,
        on_delete=models.PROTECT,
        related_name="group_topic_schedule_entries",
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.PROTECT,
        related_name="group_topic_schedule_entries",
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "teacher", "scheduled_for", "task"],
                name="uq_group_teacher_task_schedule_date",
            )
        ]
        indexes = [
            models.Index(fields=["teacher", "scheduled_for"]),
            models.Index(fields=["group", "scheduled_for"]),
        ]
        ordering = ["scheduled_for", "group__name", "teacher__user__username"]

    def clean(self):
        super().clean()
        if self.task_id and self.task.topic_id != self.topic_id:
            raise ValidationError({"task": "Task must belong to the selected topic."})

    def save(self, *args, **kwargs):
        if self.task_id:
            self.topic = self.task.topic
        elif self.topic_id and not self.task_id:
            self.task = Task.get_default_for_topic(self.topic)
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"{self.group.name} | {self.teacher.user.username} | "
            f"{self.scheduled_for.isoformat()} | {self.task.title if self.task_id else self.topic.title}"
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
def complete_attempt(sender, instance, created, **kwargs):
    if instance.status != Attempt.Status.COMPLETED:
        return

    for attempt_question in instance.attempt_questions.all():
        answer, _ = Answer.objects.get_or_create(attempt_question=attempt_question)
        answer.check_answer()
