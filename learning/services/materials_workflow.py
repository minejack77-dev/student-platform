"""Short material workflow; legacy organisation and schedules remain intact."""
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404

from learning.models import Group, GroupTeachingAssignment, GroupTopicSchedule, Subject, Task, Topic
from learning.permissions import visible_groups
from learning.services.material_access import can_edit_material


class QuickTaskInput(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    subject = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.filter(is_active=True))
    topic = serializers.PrimaryKeyRelatedField(queryset=Topic.objects.filter(is_active=True), required=False)


@transaction.atomic
def create_quick_task(user, data):
    serializer = QuickTaskInput(data=data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    subject = values['subject']
    if not can_edit_material(user, subject):
        raise PermissionDenied()
    # Serialise default-container creation and title uniqueness within this subject.
    Subject.objects.select_for_update().get(pk=subject.pk)
    topic = values.get('topic')
    if topic and (topic.subject_id != subject.pk or not topic.unit.is_active or not topic.unit.workbook.is_active):
        raise serializers.ValidationError({'topic': 'Choose an active topic in this subject.'})
    if not topic:
        unit = Topic.get_default_unit(subject)
        if not unit.is_active or not unit.workbook.is_active:
            raise serializers.ValidationError({'topic': 'The default folder is inactive. Choose an active topic.'})
        topic, _ = Topic.objects.get_or_create(subject=subject, unit=unit, title='General')
        if not topic.is_active:
            raise serializers.ValidationError({'topic': 'The default topic is inactive. Choose an active topic.'})
    if Task.objects.filter(topic=topic, title=values['title']).exists():
        raise serializers.ValidationError({'title': 'A test with this title already exists in this topic.'})
    return Task.objects.create(topic=topic, title=values['title'], questions_per_attempt=1, passing_correct_answers=1)


class AssignTaskInput(serializers.Serializer):
    group = serializers.IntegerField(min_value=1, max_value=9223372036854775807)
    date = serializers.DateField()

    def validate_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError('Choose today or a future date.')
        return value


@transaction.atomic
def assign_task(user, task, data):
    serializer = AssignTaskInput(data=data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    group = get_object_or_404(visible_groups(Group.objects.filter(is_active=True), user), pk=values['group'])
    teacher = getattr(user, 'teacher_profile', None)
    if teacher is None:
        raise PermissionDenied()
    if not (task.is_active and task.topic.is_active and task.topic.subject.is_active
            and task.topic.unit.is_active and task.topic.unit.workbook.is_active
            and task.questions.filter(is_active=True).count() >= task.questions_per_attempt):
        raise serializers.ValidationError({'code': 'task_not_ready'})
    # A group owner's first assignment establishes their teaching scope. Never
    # replace an existing assignment: its calendar and attempt history are retained.
    GroupTeachingAssignment.objects.get_or_create(group=group, teacher=teacher, defaults={
        'subject': task.topic.subject, 'workbook': task.topic.unit.workbook,
    })
    entry, created = GroupTopicSchedule.objects.get_or_create(
        group=group, teacher=teacher, scheduled_for=values['date'], task=task,
        defaults={'topic': task.topic},
    )
    if created:
        Group.objects.filter(pk=group.pk).update(updated_at=timezone.now())
    return entry, created
