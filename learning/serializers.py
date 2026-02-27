from rest_framework import serializers, status, viewsets
from learning.models import Choice, Question, Attempt, AttemptQuestion, Answer
from datetime import datetime as dt


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
    class Meta:
        model = Answer
        fields = "__all__"


class AttemptSerializer(serializers.ModelSerializer):
    correct_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Attempt
        fields = "__all__"

    def update(self, instance, validated_data):
        status = validated_data.get("status", None)
        print(status, instance.finished_at)
        if status == "completed" and instance.finished_at is None:
            validated_data["finished_at"] = dt.now()
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
