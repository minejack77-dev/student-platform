from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APITestCase
from accounts.models import User, Teacher, teacher_learning_permissions
from learning.models import Subject, Topic, Task, Question, Group, GroupTeachingAssignment, GroupTopicSchedule, Workbook


class MaterialsWorkflowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='author', role='teacher')
        self.teacher = Teacher.objects.create(user=self.user)
        self.user.user_permissions.set(teacher_learning_permissions())
        self.client.force_authenticate(self.user)
        self.subject = Subject.objects.create(name='English', owner=self.user)
        self.group = Group.objects.create(name='Class', teacher=self.teacher)

    def create(self, **extra):
        return self.client.post('/api/task/quick-create/', {'title': 'New test', 'subject': self.subject.pk, **extra})

    def ready_task(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.data)
        task = Task.objects.get(pk=response.data['id'])
        Question.objects.create(task=task, topic=task.topic, text='Question')
        return task

    def assign(self, task, **extra):
        return self.client.post(f'/api/task/{task.pk}/assign/', {'group': self.group.pk, 'date': timezone.localdate().isoformat(), **extra})

    def test_create_without_hierarchy_and_reuse_folder(self):
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual(self.create(title='Second').status_code, 201)
        self.assertEqual(Topic.objects.count(), 1)
        self.assertEqual(Workbook.objects.filter(subject=self.subject).count(), 1)
        self.assertEqual(self.create().status_code, 400)
        self.assertEqual(Task.objects.count(), 2)

    def test_reject_foreign_subject_and_mismatched_topic(self):
        foreign = Subject.objects.create(name='Other')
        self.assertEqual(self.create(subject=foreign.pk).status_code, 403)
        topic = Topic.objects.create(subject=foreign, title='Foreign')
        self.assertEqual(self.create(topic=topic.pk).status_code, 400)
        self.assertFalse(Task.objects.exists())

    def test_invalid_creation_has_no_side_effects(self):
        self.assertEqual(self.create(title='').status_code, 400)
        self.assertFalse(Workbook.objects.filter(subject=self.subject).exists())

    def test_existing_topic_is_used(self):
        topic = Topic.objects.create(subject=self.subject, title='Grammar')
        result = self.create(topic=topic.pk)
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.data['topic'], topic.pk)

    def test_assignment_is_idempotent_and_preserves_group_defaults(self):
        other = Subject.objects.create(name='Math', owner=self.user)
        assignment = GroupTeachingAssignment.objects.create(group=self.group, teacher=self.teacher, subject=other)
        task = self.ready_task()
        self.assertEqual(self.assign(task).status_code, 201)
        self.assertEqual(self.assign(task).status_code, 200)
        self.assertEqual(GroupTopicSchedule.objects.count(), 1)
        assignment.refresh_from_db()
        self.assertEqual(assignment.subject_id, other.pk)
        calendar = self.client.get(f'/api/group/{self.group.pk}/topic-calendar/')
        self.assertEqual(calendar.status_code, 200)
        self.assertEqual(calendar.data['results'][0]['task'], task.pk)

    def test_not_ready_and_past_date_rejected(self):
        task = Task.objects.get(pk=self.create().data['id'])
        self.assertEqual(self.assign(task).status_code, 400)
        Question.objects.create(task=task, topic=task.topic, text='Question')
        self.assertEqual(self.assign(task, date=(timezone.localdate() - timedelta(days=1)).isoformat()).status_code, 400)
        self.assertFalse(GroupTopicSchedule.objects.exists())
        self.assertFalse(GroupTeachingAssignment.objects.exists())

    def test_unrelated_group_and_foreign_task_rejected(self):
        task = self.ready_task()
        foreign_group = Group.objects.create(name='Unrelated')
        self.assertEqual(self.assign(task, group=foreign_group.pk).status_code, 404)
        self.subject.owner = None
        self.subject.save()
        self.assertEqual(self.assign(task).status_code, 403)
        self.assertFalse(GroupTopicSchedule.objects.exists())
