from io import BytesIO
import hashlib
import json
import secrets
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from unittest.mock import patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import User, Teacher, Student, teacher_learning_permissions
from learning.models import Subject, Topic, Task, Question, Choice, Group, GroupTopicSchedule, AttemptQuestion

EVIDENCE = []


def record(name, **data):
    EVIDENCE.append({'case': name, **data})
    print('AUDIT_V2 ' + json.dumps(EVIDENCE[-1], ensure_ascii=True), flush=True)


@override_settings(
    SECURITY_RATE_LIMITS_ENABLED=True,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'audit-v2'}},
)
class AuditV2(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = secrets.token_urlsafe(24)
        cls.owner = User.objects.create_user(username='v2_owner', password=cls.password, role='teacher')
        cls.teacher = Teacher.objects.create(user=cls.owner)
        cls.owner.user_permissions.add(*teacher_learning_permissions())
        cls.user = User.objects.create_user(username='v2_student', password=cls.password)
        cls.student = Student.objects.create(user=cls.user)
        cls.other = User.objects.create_user(username='v2_other_student', password=cls.password)
        Student.objects.create(user=cls.other)
        cls.admin = User.objects.create_superuser(username='v2_admin', password=cls.password)
        cls.subject = Subject.objects.create(name='Synthetic audit subject', owner=cls.owner)
        cls.topic = Topic.objects.create(subject=cls.subject, title='Synthetic lesson')
        cls.task = Task.objects.create(topic=cls.topic, title='Synthetic task', questions_per_attempt=1, passing_correct_answers=1)
        cls.question = Question.objects.create(topic=cls.topic, task=cls.task, text='Private synthetic question', question_type='single_choice')
        cls.correct = Choice.objects.create(question=cls.question, text='Synthetic correct', is_correct=True)
        cls.wrong = Choice.objects.create(question=cls.question, text='Synthetic wrong', is_correct=False)
        cls.group = Group.objects.create(name='Synthetic audit group', teacher=cls.teacher)
        cls.group.students.add(cls.student)
        cls.entry = GroupTopicSchedule.objects.create(group=cls.group, teacher=cls.teacher, topic=cls.topic, task=cls.task, scheduled_for=timezone.localdate())

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def login(self, user):
        client = APIClient(enforce_csrf_checks=True)
        self.assertEqual(client.get('/api/auth/csrf/').status_code, 204)
        client.credentials(HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        response = client.post('/api/auth/login/', {'username': user.username, 'password': self.password}, format='json')
        self.assertEqual(response.status_code, 200)
        client.credentials(HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        return client

    def start(self, client):
        response = client.post('/api/attempt/', {'schedule_entry': self.entry.pk}, format='json')
        self.assertEqual(response.status_code, 201, getattr(response, 'data', None))
        attempt_id = response.data['id']
        aq_id = AttemptQuestion.objects.get(attempt_id=attempt_id).pk
        return attempt_id, aq_id

    def test_v2_01_media_after_membership_revocation(self):
        with TemporaryDirectory(prefix='audit-v2-media-') as directory, override_settings(MEDIA_ROOT=directory):
            owner = self.login(self.owner)
            student = self.login(self.user)
            other = self.login(self.other)
            anonymous = APIClient(enforce_csrf_checks=True)
            image = BytesIO()
            Image.new('RGB', (3, 3), color='blue').save(image, format='PNG')
            upload = SimpleUploadedFile('synthetic-private.png', image.getvalue(), content_type='image/png')
            response = owner.post(f'/api/question/{self.question.pk}/images/', {'images': [upload]}, format='multipart')
            self.assertEqual(response.status_code, 201)
            path = urlsplit(response.data[0]['image']).path
            attempt_id, aq_id = self.start(student)

            def download(client):
                response = client.get(path)
                content = b''.join(response.streaming_content) if response.status_code == 200 else b''
                response.close()
                return response.status_code, hashlib.sha256(content).hexdigest() if content else None

            before, before_hash = download(student)
            anon_status, _ = download(anonymous)
            other_status, _ = download(other)
            removed = owner.post(f'/api/group/{self.group.pk}/remove-student/', {'user_id': self.user.pk}, format='json')
            self.assertEqual(removed.status_code, 200)
            self.assertTrue(removed.data['removed'])
            self.assertFalse(self.group.students.filter(pk=self.student.pk).exists())
            after, after_hash = download(student)
            answer = student.post('/api/answer/', {'attempt_question': aq_id, 'selected_choices': [self.correct.pk]}, format='json')
            attempt = student.get(f'/api/attempt/{attempt_id}/')
            record('V2-01', upload_status=response.status_code, anonymous=anon_status, unrelated_student=other_status,
                   member=before, removal=removed.status_code, revoked_member=after,
                   same_bytes=before_hash == after_hash, answer_after_removal=answer.status_code,
                   attempt_status=attempt.data['status'])
            self.assertEqual((anon_status, other_status, before, after, answer.status_code), (403, 404, 200, 404, 400))
            self.assertIsNone(after_hash)
            self.assertEqual(attempt.data['status'], 'in_progress')

    def test_v2_02_admin_login_respects_api_lockout(self):
        client = APIClient(enforce_csrf_checks=True)
        client.get('/api/auth/csrf/')
        csrf = client.cookies['csrftoken'].value
        client.credentials(HTTP_X_CSRFTOKEN=csrf)
        wrong = {'username': self.admin.username, 'password': 'synthetic-wrong-password'}
        statuses = [client.post('/api/auth/login/', wrong, format='json').status_code for _ in range(9)]
        self.assertEqual(statuses, [400] * 8 + [429])
        correct_api = client.post('/api/auth/login/', {'username': self.admin.username, 'password': self.password}, format='json')
        self.assertEqual(correct_api.status_code, 429)
        page = client.get('/admin/login/')
        self.assertEqual(page.status_code, 200)
        csrf = client.cookies['csrftoken'].value
        admin_statuses = []
        for _ in range(10):
            response = client.post('/admin/login/', {**wrong, 'csrfmiddlewaretoken': csrf, 'next': '/admin/'}, format='multipart')
            admin_statuses.append(response.status_code)
            self.assertIsNone(client.session.get('_auth_user_id'))
        accepted = client.post('/admin/login/', {'username': self.admin.username, 'password': self.password, 'csrfmiddlewaretoken': csrf, 'next': '/admin/'}, format='multipart')
        index = client.get('/admin/')
        record('V2-02', api_wrong_password_statuses=statuses, api_correct_password_during_lockout=correct_api.status_code,
               admin_wrong_password_statuses=admin_statuses, admin_correct_password=accepted.status_code,
               authenticated_as_target=client.session.get('_auth_user_id') == str(self.admin.pk), admin_index=index.status_code)
        self.assertEqual(admin_statuses, [429] * 10)
        self.assertEqual(accepted.status_code, 429)
        self.assertIsNone(client.session.get('_auth_user_id'))
        self.assertEqual(index.status_code, 302)

    def test_control_answer_grading_is_not_exposed_before_submit(self):
        client = self.login(self.user)
        attempt_id, aq_id = self.start(client)
        observations = []
        for choice in (self.wrong, self.correct):
            response = client.post('/api/answer/', {'attempt_question': aq_id, 'selected_choices': [choice.pk]}, format='json')
            question = client.get(f'/api/attempt_question/{aq_id}/')
            observations.append({'save': response.status_code, 'is_correct': response.data['is_correct'], 'correct_choice_ids': question.data['correct_choice_ids']})
            self.assertIsNone(response.data['is_correct'])
            self.assertEqual(question.data['correct_choice_ids'], [])
        record('CONTROL-pre-submit-grading', observations=observations)

    def test_admin_budget_blocks_api_and_expires(self):
        client = APIClient(enforce_csrf_checks=True)
        client.get('/admin/login/')
        csrf = client.cookies['csrftoken'].value
        client.credentials(HTTP_X_CSRFTOKEN=csrf)
        wrong = {'username': self.admin.username, 'password': 'wrong', 'csrfmiddlewaretoken': csrf}
        with patch('accounts.throttling.time.time', return_value=3000):
            for _ in range(8):
                self.assertEqual(client.post('/admin/login/', wrong, format='multipart').status_code, 200)
            with patch('accounts.views.authenticate') as api_authenticate:
                response = client.post('/api/auth/login/', {
                    'username': self.admin.username, 'password': self.password,
                }, format='json')
                self.assertEqual(response.status_code, 429)
                api_authenticate.assert_not_called()
            with patch('django.contrib.auth.forms.authenticate') as admin_authenticate:
                response = client.post('/admin/login/', {**wrong, 'password': self.password}, format='multipart')
                self.assertEqual(response.status_code, 429)
                self.assertGreater(int(response['Retry-After']), 0)
                admin_authenticate.assert_not_called()
        with patch('accounts.throttling.time.time', return_value=3301):
            response = client.post('/admin/login/', {**wrong, 'password': self.password}, format='multipart')
            self.assertEqual(response.status_code, 302)
            self.assertEqual(client.session.get('_auth_user_id'), str(self.admin.pk))

    def test_completed_media_remains_readable_after_membership_revocation(self):
        with TemporaryDirectory(prefix='completed-media-') as directory, override_settings(MEDIA_ROOT=directory):
            owner, student = self.login(self.owner), self.login(self.user)
            image = BytesIO()
            Image.new('RGB', (3, 3), color='blue').save(image, format='PNG')
            response = owner.post(f'/api/question/{self.question.pk}/images/', {
                'images': [SimpleUploadedFile('history.png', image.getvalue(), content_type='image/png')],
            }, format='multipart')
            self.assertEqual(response.status_code, 201)
            path = urlsplit(response.data[0]['image']).path
            attempt_id, aq_id = self.start(student)
            response = student.post(f'/api/attempt/{attempt_id}/submit/', {'answers': [{
                'attempt_question': aq_id, 'selected_choices': [self.correct.pk],
            }]}, format='json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(owner.post(f'/api/group/{self.group.pk}/remove-student/', {
                'user_id': self.user.pk,
            }, format='json').status_code, 200)
            response = student.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(b''.join(response.streaming_content))
            response.close()

    def test_disabled_assignment_revokes_unfinished_media(self):
        with TemporaryDirectory(prefix='revoked-media-') as directory, override_settings(MEDIA_ROOT=directory):
            owner, student = self.login(self.owner), self.login(self.user)
            image = BytesIO()
            Image.new('RGB', (3, 3), color='blue').save(image, format='PNG')
            response = owner.post(f'/api/question/{self.question.pk}/images/', {
                'images': [SimpleUploadedFile('active.png', image.getvalue(), content_type='image/png')],
            }, format='multipart')
            self.assertEqual(response.status_code, 201)
            path = urlsplit(response.data[0]['image']).path
            self.start(student)
            for obj in (self.group, self.subject, self.topic, self.task):
                with self.subTest(model=type(obj).__name__):
                    obj.is_active = False
                    obj.save(update_fields=['is_active'])
                    self.assertEqual(student.get(path).status_code, 404)
                    obj.is_active = True
                    obj.save(update_fields=['is_active'])

    def test_control_foreign_attempt_access_and_write_denied(self):
        student = self.login(self.user)
        other = self.login(self.other)
        attempt_id, aq_id = self.start(student)
        detail = other.get(f'/api/attempt/{attempt_id}/')
        question = other.get(f'/api/attempt_question/{aq_id}/')
        write = other.post('/api/answer/', {'attempt_question': aq_id, 'selected_choices': [self.correct.pk]}, format='json')
        record('CONTROL-foreign-attempt', attempt=detail.status_code, question=question.status_code, answer_write=write.status_code)
        self.assertEqual((detail.status_code, question.status_code, write.status_code), (404, 404, 400))

    def test_control_snapshots_preserve_graded_answer_after_bank_edit(self):
        student = self.login(self.user)
        owner = self.login(self.owner)
        attempt_id, aq_id = self.start(student)
        response = student.post(f'/api/attempt/{attempt_id}/submit/', {'answers': [{'attempt_question': aq_id, 'selected_choices': [self.correct.pk]}]}, format='json')
        self.assertEqual(response.status_code, 200)
        before = student.get(f'/api/attempt_question/{aq_id}/').data
        edit = owner.patch(f'/api/question/{self.question.pk}/', {'text': 'Changed bank question', 'choices': [
            {'text': 'New wrong', 'is_correct': False}, {'text': 'New correct', 'is_correct': True}
        ]}, format='json')
        self.assertEqual(edit.status_code, 200)
        after = student.get(f'/api/attempt_question/{aq_id}/').data
        self.assertEqual(before['question'], after['question'])
        self.assertEqual(before['correct_choice_ids'], after['correct_choice_ids'])
        self.assertEqual(before['answer'], after['answer'])
        self.assertTrue(after['answer']['is_correct'])
        record('CONTROL-snapshot-edit', edit=edit.status_code, old_question_preserved=True, old_answer_preserved=True, grade_preserved=True)
