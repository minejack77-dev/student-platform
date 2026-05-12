from django.db import transaction
from django.utils import timezone

from rest_framework import serializers

from accounts.models import Student, Teacher
from learning.models import (
    Answer,
    Attempt,
    AttemptQuestion,
    Choice,
    Group,
    GroupTopicSchedule,
    GroupTeachingAssignment,
    Question,
    Subject,
    Topic,
    Unit,
    Workbook,
)


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = "__all__"


class WorkbookSerializer(serializers.ModelSerializer):
    subject = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.filter(is_active=True),
    )
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = Workbook
        fields = (
            "id",
            "subject",
            "subject_name",
            "title",
            "description",
            "is_active",
            "updated_at",
        )
        read_only_fields = ("id", "subject_name", "updated_at")


class UnitSerializer(serializers.ModelSerializer):
    workbook = serializers.PrimaryKeyRelatedField(
        queryset=Workbook.objects.filter(is_active=True),
    )
    workbook_title = serializers.CharField(source="workbook.title", read_only=True)
    subject = serializers.IntegerField(source="workbook.subject_id", read_only=True)
    subject_name = serializers.CharField(source="workbook.subject.name", read_only=True)

    class Meta:
        model = Unit
        fields = (
            "id",
            "workbook",
            "workbook_title",
            "subject",
            "subject_name",
            "title",
            "description",
            "is_active",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "workbook_title",
            "subject",
            "subject_name",
            "updated_at",
        )


class GroupTeachingAssignmentSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)
    teacher_username = serializers.CharField(
        source="teacher.user.username", read_only=True
    )
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    topic_title = serializers.CharField(source="topic.title", read_only=True)

    class Meta:
        model = GroupTeachingAssignment
        fields = (
            "id",
            "group",
            "group_name",
            "teacher",
            "teacher_username",
            "subject",
            "subject_name",
            "topic",
            "topic_title",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "group",
            "group_name",
            "teacher",
            "teacher_username",
            "subject_name",
            "topic_title",
            "updated_at",
        )


class GroupTopicScheduleSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)
    teacher_username = serializers.CharField(
        source="teacher.user.username", read_only=True
    )
    date = serializers.DateField(source="scheduled_for", read_only=True)
    subject = serializers.IntegerField(source="topic.subject_id", read_only=True)
    subject_name = serializers.CharField(source="topic.subject.name", read_only=True)
    topic_title = serializers.CharField(source="topic.title", read_only=True)

    class Meta:
        model = GroupTopicSchedule
        fields = (
            "id",
            "group",
            "group_name",
            "teacher",
            "teacher_username",
            "date",
            "subject",
            "subject_name",
            "topic",
            "topic_title",
            "updated_at",
        )
        read_only_fields = fields


class GroupTopicScheduleWriteSerializer(serializers.Serializer):
    date = serializers.DateField()
    topic = serializers.PrimaryKeyRelatedField(
        queryset=Topic.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        if "topic" not in attrs:
            raise serializers.ValidationError({"topic": "This field is required."})
        return attrs


class TopicSerializer(serializers.ModelSerializer):
    subject = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.filter(is_active=True),
        required=False,
    )
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    unit = serializers.PrimaryKeyRelatedField(
        queryset=Unit.objects.filter(is_active=True),
        required=False,
    )
    unit_title = serializers.CharField(source="unit.title", read_only=True)
    workbook = serializers.IntegerField(source="unit.workbook_id", read_only=True)
    workbook_title = serializers.CharField(source="unit.workbook.title", read_only=True)

    class Meta:
        model = Topic
        fields = (
            "id",
            "subject",
            "subject_name",
            "workbook",
            "workbook_title",
            "unit",
            "unit_title",
            "title",
            "description",
            "is_active",
            "updated_at",
        )
        validators = []
        read_only_fields = (
            "id",
            "updated_at",
            "subject_name",
            "workbook",
            "workbook_title",
            "unit_title",
        )

    def _validate_unique_title(self, unit, title):
        if unit is None or not title:
            return

        queryset = Topic.objects.filter(unit=unit, title=title)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                {"title": "Topic with this title already exists in the selected unit."}
            )

    def validate(self, attrs):
        current_subject = getattr(self.instance, "subject", None)
        current_unit = getattr(self.instance, "unit", None)
        title = attrs.get("title", getattr(self.instance, "title", None))

        subject_provided = "subject" in attrs
        unit_provided = "unit" in attrs

        subject = attrs.get("subject", current_subject)
        unit = attrs.get("unit", current_unit)

        if unit is not None:
            unit_subject = unit.workbook.subject
            if subject_provided and subject is not None and subject.id != unit_subject.id:
                raise serializers.ValidationError(
                    {"unit": "Unit must belong to the selected subject."}
                )
            attrs["subject"] = unit_subject
            self._validate_unique_title(unit, title)
            return attrs

        if self.instance is None:
            if subject is None:
                raise serializers.ValidationError(
                    {"subject": "Subject is required when unit is not set."}
                )
            attrs["unit"] = Topic.get_default_unit(subject)
            self._validate_unique_title(attrs["unit"], title)
            return attrs

        if subject_provided and subject is not None and not unit_provided:
            attrs["unit"] = Topic.get_default_unit(subject)

        self._validate_unique_title(attrs.get("unit", unit), title)
        return attrs


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ("id", "text", "is_correct", "order")
        read_only_fields = ("id",)


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True)

    class Meta:
        model = Question
        fields = (
            "id",
            "topic",
            "instruction",
            "text",
            "question_type",
            "is_active",
            "created_at",
            "choices",
        )
        read_only_fields = ("id", "created_at")

    def validate_choices(self, choices):
        if not choices:
            raise serializers.ValidationError("At least one answer choice is required.")
        for idx, choice in enumerate(choices, start=1):
            text = (choice.get("text") or "").strip()
            if not text:
                raise serializers.ValidationError(
                    f"Choice #{idx} must have non-empty text."
                )
        return choices

    def validate(self, attrs):
        question_type = attrs.get(
            "question_type",
            getattr(
                self.instance, "question_type", Question.QuestionType.MULTIPLE_CHOICE
            ),
        )
        choices = attrs.get("choices")
        if self.instance is None and choices is None:
            raise serializers.ValidationError({"choices": "This field is required."})
        if choices is None:
            return attrs

        if len(choices) < 2:
            raise serializers.ValidationError(
                {"choices": "At least two answer choices are required."}
            )

        correct_count = sum(1 for choice in choices if choice.get("is_correct"))
        if question_type == Question.QuestionType.SINGLE_CHOICE and correct_count != 1:
            raise serializers.ValidationError(
                {
                    "choices": "Single choice question must have exactly one correct choice."
                }
            )
        if question_type == Question.QuestionType.MULTIPLE_CHOICE and correct_count < 1:
            raise serializers.ValidationError(
                {
                    "choices": "Multiple choice question must have at least one correct choice."
                }
            )
        return attrs

    def _replace_choices(self, question, choices_data):
        question.choices.all().delete()
        for idx, choice in enumerate(choices_data, start=1):
            Choice.objects.create(
                question=question,
                text=choice["text"].strip(),
                is_correct=choice.get("is_correct", False),
                order=choice.get("order") or idx,
            )

    def create(self, validated_data):
        choices_data = validated_data.pop("choices")
        question = Question.objects.create(**validated_data)
        self._replace_choices(question, choices_data)
        return question

    def update(self, instance, validated_data):
        choices_data = validated_data.pop("choices", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if choices_data is not None:
            self._replace_choices(instance, choices_data)
        return instance


class AnswerSerializer(serializers.ModelSerializer):
    selected_choices = serializers.PrimaryKeyRelatedField(
        queryset=Choice.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = Answer
        fields = (
            "id",
            "attempt_question",
            "selected_choices",
            "answered_at",
            "is_correct",
            "teacher_comment",
        )
        read_only_fields = ("id", "answered_at", "is_correct", "teacher_comment")

    def validate(self, attrs):
        attempt_question = attrs.get("attempt_question")
        if self.instance is not None:
            if (
                attempt_question is not None
                and attempt_question.id != self.instance.attempt_question_id
            ):
                raise serializers.ValidationError(
                    {"attempt_question": "Attempt question cannot be changed."}
                )
            attempt_question = self.instance.attempt_question

        if attempt_question is None:
            raise serializers.ValidationError(
                {"attempt_question": "This field is required."}
            )

        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        if not user or not user.is_authenticated:
            raise serializers.ValidationError({"detail": "Authentication required."})

        try:
            student = user.student_profile
        except Student.DoesNotExist:
            raise serializers.ValidationError(
                {"detail": "Only students can submit answers."}
            )

        if attempt_question.attempt.student_id != student.id:
            raise serializers.ValidationError(
                {"attempt_question": "This question does not belong to your attempt."}
            )

        if attempt_question.attempt.status != Attempt.Status.IN_PROGRESS:
            raise serializers.ValidationError(
                {"attempt_question": "Attempt is already finished."}
            )
        if not attempt_question.attempt.is_accessible_on(timezone.localdate()):
            raise serializers.ValidationError(
                {
                    "detail": (
                        "This test can only be completed on its scheduled date."
                    )
                }
            )

        selected_choices = attrs.get("selected_choices")
        if selected_choices is not None:
            valid_choice_ids = set(
                attempt_question.question.choices.values_list("id", flat=True)
            )
            selected_choice_ids = {choice.id for choice in selected_choices}
            if not selected_choice_ids.issubset(valid_choice_ids):
                raise serializers.ValidationError(
                    {"selected_choices": "Choices must belong to the question."}
                )

            if (
                attempt_question.question.question_type
                == Question.QuestionType.SINGLE_CHOICE
                and len(selected_choice_ids) > 1
            ):
                raise serializers.ValidationError(
                    {"selected_choices": "Only one choice is allowed for this question."}
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        selected_choices = validated_data.pop("selected_choices", [])
        attempt_question = validated_data.pop("attempt_question")

        answer, _ = Answer.objects.get_or_create(
            attempt_question=attempt_question,
        )
        for key, value in validated_data.items():
            setattr(answer, key, value)
        answer.save()
        answer.selected_choices.set(selected_choices)
        return answer

    @transaction.atomic
    def update(self, instance, validated_data):
        selected_choices = validated_data.pop("selected_choices", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if selected_choices is not None:
            instance.selected_choices.set(selected_choices)
        return instance


class AttemptSerializer(serializers.ModelSerializer):
    schedule_entry = serializers.PrimaryKeyRelatedField(
        queryset=GroupTopicSchedule.objects.select_related(
            "group",
            "teacher__user",
            "topic",
            "topic__subject",
        ),
        write_only=True,
        required=False,
        allow_null=True,
    )
    schedule_entry_id = serializers.IntegerField(read_only=True)
    schedule_date = serializers.DateField(source="schedule_entry.scheduled_for", read_only=True)
    schedule_group_name = serializers.CharField(source="schedule_entry.group.name", read_only=True)
    schedule_teacher_username = serializers.CharField(
        source="schedule_entry.teacher.user.username", read_only=True
    )
    topic = serializers.PrimaryKeyRelatedField(
        queryset=Topic.objects.filter(is_active=True),
        required=False,
    )
    subject = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.filter(is_active=True),
        write_only=True,
        required=False,
        allow_null=True,
    )
    subject_name = serializers.CharField(source="topic.subject.name", read_only=True)
    topic_title = serializers.CharField(source="topic.title", read_only=True)
    correct_count = serializers.SerializerMethodField(read_only=True)
    wrong_count = serializers.SerializerMethodField(read_only=True)
    total_questions = serializers.SerializerMethodField(read_only=True)
    result_outcome = serializers.SerializerMethodField(read_only=True)
    can_interact_today = serializers.SerializerMethodField(read_only=True)
    passing_correct_answers = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Attempt
        fields = (
            "id",
            "student",
            "schedule_entry",
            "schedule_entry_id",
            "schedule_date",
            "schedule_group_name",
            "schedule_teacher_username",
            "topic",
            "subject",
            "subject_name",
            "topic_title",
            "started_at",
            "finished_at",
            "status",
            "correct_count",
            "wrong_count",
            "total_questions",
            "result_outcome",
            "can_interact_today",
            "passing_correct_answers",
        )
        read_only_fields = (
            "id",
            "student",
            "schedule_entry_id",
            "schedule_date",
            "schedule_group_name",
            "schedule_teacher_username",
            "started_at",
            "finished_at",
            "subject_name",
            "topic_title",
            "correct_count",
            "wrong_count",
            "total_questions",
            "result_outcome",
            "can_interact_today",
            "passing_correct_answers",
        )

    def get_correct_count(self, obj):
        return obj.attempt_questions.filter(answer__is_correct=True).count()

    def get_total_questions(self, obj):
        return obj.attempt_questions.count()

    def get_wrong_count(self, obj):
        return self.get_total_questions(obj) - self.get_correct_count(obj)

    def get_result_outcome(self, obj):
        success = obj.is_successful()
        if success is None:
            return None
        return "success" if success else "fail"

    def get_can_interact_today(self, obj):
        if obj.status != Attempt.Status.IN_PROGRESS:
            return False
        return obj.is_accessible_on(timezone.localdate())

    def get_passing_correct_answers(self, _obj):
        return Attempt.PASSING_CORRECT_ANSWERS

    def validate_topic(self, value):
        if not value.is_active:
            raise serializers.ValidationError("Topic must be active.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        if not user or not user.is_authenticated:
            raise serializers.ValidationError({"detail": "Authentication required."})

        try:
            student = user.student_profile
        except Student.DoesNotExist:
            raise serializers.ValidationError(
                {"detail": "Only students can start attempts."}
            )

        schedule_entry = validated_data.pop("schedule_entry", None)
        if schedule_entry is None:
            raise serializers.ValidationError(
                {"schedule_entry": "This field is required."}
            )

        subject = validated_data.pop("subject", None)
        topic = validated_data.pop("topic", None) or schedule_entry.topic
        if topic.id != schedule_entry.topic_id:
            raise serializers.ValidationError(
                {"topic": "Topic must match the scheduled task."}
            )
        if not topic.is_active:
            raise serializers.ValidationError(
                {"topic": "Topic must be active."}
            )
        if subject and topic.subject_id != subject.id:
            raise serializers.ValidationError(
                {"topic": "Topic must belong to the selected subject."}
            )
        if schedule_entry.topic.subject_id != topic.subject_id:
            raise serializers.ValidationError(
                {"schedule_entry": "Schedule entry subject does not match the topic."}
            )
        if not schedule_entry.group.students.filter(id=student.id).exists():
            raise serializers.ValidationError(
                {"schedule_entry": "This scheduled task is not assigned to your account."}
            )

        current_date = timezone.localdate()
        if schedule_entry.scheduled_for > current_date:
            raise serializers.ValidationError(
                {"detail": "This test is not available yet."}
            )
        if schedule_entry.scheduled_for < current_date:
            raise serializers.ValidationError(
                {"detail": "This test date has already passed and can no longer be completed."}
            )
        if Attempt.objects.filter(student=student, schedule_entry=schedule_entry).exists():
            raise serializers.ValidationError(
                {"detail": "You already have an attempt for this scheduled test."}
            )

        active_questions_qs = Question.objects.filter(topic=topic, is_active=True)
        if active_questions_qs.count() < 10:
            raise serializers.ValidationError(
                {"topic": "At least 10 active questions are required for this topic."}
            )

        questions = list(active_questions_qs.order_by("?")[:10])
        attempt = Attempt.objects.create(
            student=student,
            topic=topic,
            schedule_entry=schedule_entry,
            status=Attempt.Status.IN_PROGRESS,
        )
        AttemptQuestion.objects.bulk_create(
            [
                AttemptQuestion(attempt=attempt, question=question, order=index)
                for index, question in enumerate(questions, start=1)
            ]
        )
        return attempt

    def update(self, instance, validated_data):
        status = validated_data.get("status", None)
        if (
            instance.status == Attempt.Status.COMPLETED
            and status
            and status != Attempt.Status.COMPLETED
        ):
            raise serializers.ValidationError(
                {"status": "Completed attempt status cannot be changed."}
            )
        if (
            instance.status == Attempt.Status.IN_PROGRESS
            and status == Attempt.Status.COMPLETED
            and not instance.is_accessible_on(timezone.localdate())
        ):
            raise serializers.ValidationError(
                {
                    "detail": (
                        "This test can only be completed on its scheduled date."
                    )
                }
            )
        if (
            status == Attempt.Status.COMPLETED
            and instance.finished_at is None
        ):
            validated_data["finished_at"] = timezone.now()
        return super().update(instance, validated_data)


class ChoiceInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ("id", "text", "order")
        read_only_fields = ("id",)


class QuestionInlineSerializer(serializers.ModelSerializer):
    choices = ChoiceInlineSerializer(many=True)

    class Meta:
        model = Question
        fields = (
            "id",
            "topic",
            "instruction",
            "text",
            "question_type",
            "is_active",
            "created_at",
            "choices",
        )
        read_only_fields = ("id", "created_at")


class AttemptQuestionSerializer(serializers.ModelSerializer):
    question = QuestionInlineSerializer(read_only=True)
    answer = AnswerSerializer(read_only=True)

    class Meta:
        model = AttemptQuestion
        fields = "__all__"


class GroupSerializer(serializers.ModelSerializer):
    teacher_assignment = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = (
            "id",
            "name",
            "description",
            "teacher",
            "teacher_assignment",
            "is_active",
            "updated_at",
        )
        read_only_fields = ("id", "updated_at", "teacher_assignment")

    def _get_teacher(self):
        cached_teacher = self.context.get("_request_teacher")
        if cached_teacher is not None:
            return cached_teacher

        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        if not user or not user.is_authenticated:
            self.context["_request_teacher"] = None
            return None

        try:
            teacher = user.teacher_profile
        except Teacher.DoesNotExist:
            teacher = None
        self.context["_request_teacher"] = teacher
        return teacher

    def _get_teacher_assignment(self, obj):
        teacher = self._get_teacher()
        if not teacher:
            return None

        cache_attr = f"_assignment_for_teacher_{teacher.id}"
        if hasattr(obj, cache_attr):
            return getattr(obj, cache_attr)

        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get(
            "teaching_assignments"
        )
        if prefetched is not None:
            assignment = next(
                (item for item in prefetched if item.teacher_id == teacher.id),
                None,
            )
        else:
            assignment = (
                obj.teaching_assignments.select_related("subject", "topic", "teacher__user")
                .filter(teacher_id=teacher.id)
                .first()
            )
        setattr(obj, cache_attr, assignment)
        return assignment

    def get_teacher_assignment(self, obj):
        assignment = self._get_teacher_assignment(obj)
        if not assignment:
            return None
        return {
            "id": assignment.id,
            "teacher": assignment.teacher_id,
            "teacher_username": assignment.teacher.user.username,
            "subject": assignment.subject_id,
            "subject_name": assignment.subject.name,
            "topic": assignment.topic_id,
            "topic_title": assignment.topic.title if assignment.topic else None,
            "updated_at": assignment.updated_at,
        }


class GroupTeachingAssignmentWriteSerializer(serializers.Serializer):
    subject = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    topic = serializers.PrimaryKeyRelatedField(
        queryset=Topic.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        current_subject = getattr(self.instance, "subject", None)
        current_topic = getattr(self.instance, "topic", None)

        subject_provided = "subject" in attrs
        topic_provided = "topic" in attrs

        subject = attrs.get("subject", current_subject)
        topic = attrs.get("topic", current_topic)

        if subject_provided and attrs.get("subject") is None and not topic_provided:
            attrs["topic"] = None
            topic = None

        if subject is None and topic is not None:
            raise serializers.ValidationError(
                {"subject": "Subject is required when topic is set."}
            )
        if topic and subject and topic.subject_id != subject.id:
            raise serializers.ValidationError(
                {"topic": "Topic must belong to the selected subject."}
            )

        # If only subject changed and the old topic no longer belongs to it, clear topic.
        if (
            subject_provided
            and not topic_provided
            and current_topic
            and subject
            and current_topic.subject_id != subject.id
        ):
            attrs["topic"] = None
        return attrs


class StudentBriefSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Student
        fields = ("id", "user", "username", "email")


class GroupDetailSerializer(GroupSerializer):
    students = StudentBriefSerializer(many=True, read_only=True)

    class Meta(GroupSerializer.Meta):
        fields = GroupSerializer.Meta.fields + ("students",)
        read_only_fields = GroupSerializer.Meta.read_only_fields + ("students",)
