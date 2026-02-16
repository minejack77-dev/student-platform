from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters import FilterSet, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from accounts.models import Student, Teacher
from learning.models import Choice, Group, GroupTeachingAssignment, Question, Subject, Topic


def get_request_teacher(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None
    try:
        return user.teacher_profile
    except Teacher.DoesNotExist:
        return None


class SubjectSetFilter(FilterSet):
    name = filters.CharFilter(field_name="name", lookup_expr="icontains")

    class Meta:
        model = Subject
        fields = ("id", "name", "is_active")


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = "__all__"


class GroupTeachingAssignmentSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)
    teacher_username = serializers.CharField(source="teacher.user.username", read_only=True)
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


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = SubjectSetFilter
    ordering_fields = ("name", "updated_at", "id")
    ordering = ("name",)

    @action(detail=True, methods=["get"], url_path="groups")
    def groups(self, request, pk=None):
        teacher = get_request_teacher(request)
        if not teacher:
            return Response(
                {"detail": "Only teachers can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        assignments = (
            GroupTeachingAssignment.objects.select_related("group", "teacher__user", "subject", "topic")
            .filter(teacher=teacher, subject_id=pk)
            .order_by("group__name")
        )
        serializer = GroupTeachingAssignmentSerializer(assignments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TopicSetFilter(FilterSet):
    title = filters.CharFilter(field_name="title", lookup_expr="icontains")
    subject = filters.NumberFilter(field_name="subject_id")

    class Meta:
        model = Topic
        fields = ("id", "title", "subject", "is_active")


class TopicSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = Topic
        fields = (
            "id",
            "subject",
            "subject_name",
            "title",
            "description",
            "is_active",
            "updated_at",
        )
        read_only_fields = ("id", "updated_at", "subject_name")


class TopicViewSet(viewsets.ModelViewSet):
    queryset = Topic.objects.select_related("subject").all()
    serializer_class = TopicSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = TopicSetFilter
    ordering_fields = ("title", "updated_at", "id", "subject")
    ordering = ("title",)


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ("id", "text", "is_correct", "order")
        read_only_fields = ("id",)


class QuestionSetFilter(FilterSet):
    topic = filters.NumberFilter(field_name="topic_id")
    text = filters.CharFilter(field_name="text", lookup_expr="icontains")
    question_type = filters.ChoiceFilter(
        field_name="question_type", choices=Question.QuestionType.choices
    )

    class Meta:
        model = Question
        fields = ("id", "topic", "text", "question_type", "is_active")


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
            getattr(self.instance, "question_type", Question.QuestionType.MULTIPLE_CHOICE),
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
                {"choices": "Single choice question must have exactly one correct choice."}
            )
        if question_type == Question.QuestionType.MULTIPLE_CHOICE and correct_count < 1:
            raise serializers.ValidationError(
                {"choices": "Multiple choice question must have at least one correct choice."}
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


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = (
        Question.objects.select_related("topic", "topic__subject")
        .prefetch_related("choices")
        .all()
    )
    serializer_class = QuestionSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = QuestionSetFilter
    ordering = ("-created_at",)

    def _touch_topic(self, topic_id):
        Topic.objects.filter(id=topic_id).update(updated_at=timezone.now())

    def perform_create(self, serializer):
        question = serializer.save()
        self._touch_topic(question.topic_id)

    def perform_update(self, serializer):
        question = serializer.save()
        self._touch_topic(question.topic_id)

    def perform_destroy(self, instance):
        topic_id = instance.topic_id
        instance.delete()
        self._touch_topic(topic_id)


class GroupSetFilter(FilterSet):
    title = filters.CharFilter(field_name="name", lookup_expr="icontains")
    name = filters.CharFilter(field_name="name", lookup_expr="icontains")
    teacher_subject = filters.NumberFilter(method="filter_teacher_subject")
    teacher_topic = filters.NumberFilter(method="filter_teacher_topic")

    class Meta:
        model = Group
        fields = ("id", "name", "teacher", "is_active", "teacher_subject", "teacher_topic")

    def _get_teacher(self):
        request = getattr(self, "request", None)
        if not request:
            return None
        return get_request_teacher(request)

    def filter_teacher_subject(self, queryset, _name, value):
        teacher = self._get_teacher()
        if not teacher:
            return queryset.none()
        return queryset.filter(
            teaching_assignments__teacher_id=teacher.id,
            teaching_assignments__subject_id=value,
        ).distinct()

    def filter_teacher_topic(self, queryset, _name, value):
        teacher = self._get_teacher()
        if not teacher:
            return queryset.none()
        return queryset.filter(
            teaching_assignments__teacher_id=teacher.id,
            teaching_assignments__topic_id=value,
        ).distinct()


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
        teacher = get_request_teacher(request) if request else None
        self.context["_request_teacher"] = teacher
        return teacher

    def _get_teacher_assignment(self, obj):
        teacher = self._get_teacher()
        if not teacher:
            return None

        cache_attr = f"_assignment_for_teacher_{teacher.id}"
        if hasattr(obj, cache_attr):
            return getattr(obj, cache_attr)

        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get("teaching_assignments")
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


class GroupViewSet(viewsets.ModelViewSet):
    queryset = (
        Group.objects.select_related("teacher__user")
        .prefetch_related(
            "students__user",
            "teaching_assignments__subject",
            "teaching_assignments__topic",
            "teaching_assignments__teacher__user",
        )
        .all()
    )
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = GroupSetFilter
    ordering_fields = ("name", "updated_at", "id")
    ordering = ("name",)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return GroupDetailSerializer
        return GroupSerializer

    def _touch_group(self, group_id):
        Group.objects.filter(id=group_id).update(updated_at=timezone.now())

    @action(detail=True, methods=["get", "patch", "put", "delete"], url_path="teacher-assignment")
    def teacher_assignment(self, request, pk=None):
        teacher = get_request_teacher(request)
        if not teacher:
            return Response(
                {"detail": "Only teachers can manage assignments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        group = self.get_object()
        assignment = (
            GroupTeachingAssignment.objects.select_related("group", "teacher__user", "subject", "topic")
            .filter(group=group, teacher=teacher)
            .first()
        )

        if request.method == "GET":
            if not assignment:
                return Response(
                    {
                        "group": group.id,
                        "group_name": group.name,
                        "teacher": teacher.id,
                        "teacher_username": teacher.user.username,
                        "subject": None,
                        "subject_name": None,
                        "topic": None,
                        "topic_title": None,
                        "updated_at": None,
                    },
                    status=status.HTTP_200_OK,
                )
            serializer = GroupTeachingAssignmentSerializer(assignment)
            return Response(serializer.data, status=status.HTTP_200_OK)

        if request.method == "DELETE":
            if assignment:
                assignment.delete()
                self._touch_group(group.id)
            return Response(status=status.HTTP_204_NO_CONTENT)

        write_serializer = GroupTeachingAssignmentWriteSerializer(
            instance=assignment,
            data=request.data,
            partial=request.method == "PATCH",
        )
        write_serializer.is_valid(raise_exception=True)

        subject = write_serializer.validated_data.get(
            "subject",
            getattr(assignment, "subject", None),
        )
        topic = write_serializer.validated_data.get(
            "topic",
            getattr(assignment, "topic", None),
        )

        if subject is None and topic is None:
            if assignment:
                assignment.delete()
                self._touch_group(group.id)
            return Response(
                {
                    "group": group.id,
                    "group_name": group.name,
                    "teacher": teacher.id,
                    "teacher_username": teacher.user.username,
                    "subject": None,
                    "subject_name": None,
                    "topic": None,
                    "topic_title": None,
                    "updated_at": None,
                },
                status=status.HTTP_200_OK,
            )

        created = False
        if assignment is None:
            assignment = GroupTeachingAssignment(
                group=group,
                teacher=teacher,
                subject=subject,
                topic=topic,
            )
            created = True
        else:
            assignment.subject = subject
            assignment.topic = topic
        assignment.save()
        self._touch_group(group.id)

        serializer = GroupTeachingAssignmentSerializer(assignment)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="search-students")
    def search_students(self, request, pk=None):
        query = (request.query_params.get("q") or "").strip()
        if not query:
            return Response([], status=status.HTTP_200_OK)

        group = self.get_object()
        students_qs = Student.objects.select_related("user")

        if query.isdigit():
            students_qs = students_qs.filter(
                Q(user_id=int(query)) | Q(user__username__icontains=query)
            )
        else:
            students_qs = students_qs.filter(user__username__icontains=query)

        students = list(students_qs.order_by("user__username")[:20])
        in_group_student_ids = set(group.students.values_list("id", flat=True))

        payload = []
        for student in students:
            data = StudentBriefSerializer(student).data
            data["in_group"] = student.id in in_group_student_ids
            payload.append(data)

        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="find-student")
    def find_student(self, request, pk=None):
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response(
                {"detail": "Query parameter 'user_id' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        group = self.get_object()
        student = get_object_or_404(Student.objects.select_related("user"), user_id=user_id)
        data = StudentBriefSerializer(student).data
        data["in_group"] = group.students.filter(id=student.id).exists()
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="add-student")
    def add_student(self, request, pk=None):
        user_id = request.data.get("user_id")
        if not user_id:
            return Response(
                {"detail": "Field 'user_id' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        group = self.get_object()
        student = get_object_or_404(Student.objects.select_related("user"), user_id=user_id)
        is_member = group.students.filter(id=student.id).exists()
        if not is_member:
            group.students.add(student)
            self._touch_group(group.id)

        return Response(
            {
                "added": not is_member,
                "student": StudentBriefSerializer(student).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="remove-student")
    def remove_student(self, request, pk=None):
        user_id = request.data.get("user_id")
        if not user_id:
            return Response(
                {"detail": "Field 'user_id' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        group = self.get_object()
        student = get_object_or_404(Student.objects.select_related("user"), user_id=user_id)
        is_member = group.students.filter(id=student.id).exists()
        if is_member:
            group.students.remove(student)
            self._touch_group(group.id)

        return Response(
            {
                "removed": is_member,
                "student": StudentBriefSerializer(student).data,
            },
            status=status.HTTP_200_OK,
        )
