from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User, Teacher, Student, teacher_learning_permissions
from learning.models import Subject, Topic, Task, Question, Choice, Group, GroupTopicSchedule, GroupTeachingAssignment, Attempt, AttemptQuestion, Answer
from learning.services.safe_import import import_batch, undo_batch
from learning.services.question_import import SpreadsheetCell


class UXRegressionTests(APITestCase):
    def setUp(self):
        self.teacher_user = User.objects.create_user(username='ux_teacher', role=User.Role.TEACHER)
        self.teacher = Teacher.objects.create(user=self.teacher_user)
        self.teacher_user.user_permissions.add(*teacher_learning_permissions())
        self.student_user = User.objects.create_user(username='ux_student', role=User.Role.STUDENT)
        self.student = Student.objects.create(user=self.student_user)
        self.subject = Subject.objects.create(name='UX', owner=self.teacher_user)
        self.topic = Topic.objects.create(subject=self.subject, title='Lesson')
        self.task = Task.objects.create(topic=self.topic, title='Task', questions_per_attempt=1, passing_correct_answers=1)
        self.group = Group.objects.create(name='Group', teacher=self.teacher)
        self.group.students.add(self.student)
        self.entry = GroupTopicSchedule.objects.create(group=self.group, teacher=self.teacher, topic=self.topic, task=self.task, scheduled_for=timezone.localdate())
        self.question = Question.objects.create(topic=self.topic, task=self.task, text='Question')
        self.correct = Choice.objects.create(question=self.question, text='Correct', is_correct=True, order=1)
        Choice.objects.create(question=self.question, text='Wrong', is_correct=False, order=2)
        self.attempt = Attempt.objects.create(student=self.student, task=self.task, topic=self.topic, schedule_entry=self.entry)
        self.aq = AttemptQuestion.objects.create(attempt=self.attempt, question=self.question, order=1)
        self.client.force_authenticate(self.student_user)

    def test_atomic_submit_persists_snapshot_grades_and_is_idempotent(self):
        # The usual browser flow has already autosaved an answer.
        saved = Answer.objects.create(attempt_question=self.aq)
        saved.selected_choices.add(self.question.choices.get(is_correct=False))
        payload = {'answers': [{'attempt_question': self.aq.id, 'selected_choices': [self.correct.id]}]}
        url = f'/api/attempt/{self.attempt.id}/submit/'
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['correct_count'], 1)
        self.assertEqual(response.data['status'], 'completed')
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 200)
        self.assertEqual(Answer.objects.filter(attempt_question=self.aq).count(), 1)

    def test_invalid_snapshot_and_unconfirmed_blank_leave_attempt_open(self):
        url = f'/api/attempt/{self.attempt.id}/submit/'
        for answers in ([], [{'attempt_question': [], 'selected_choices': []}], [{'attempt_question': self.aq.id, 'selected_choices': []}], [{'attempt_question': self.aq.id, 'selected_choices': [999999]}]):
            response = self.client.post(url, {'answers': answers}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
            self.attempt.refresh_from_db()
            self.assertEqual(self.attempt.status, 'in_progress')
            self.assertFalse(Answer.objects.filter(attempt_question=self.aq).exists())

    def test_teacher_review_scope_and_write_protection(self):
        self.client.force_authenticate(self.teacher_user)
        url = f'/api/attempt/{self.attempt.id}/'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.patch(url, {'status': 'completed'}, format='json').status_code, 403)
        self.assertEqual(self.client.post(url+'submit/', {'answers': []}, format='json').status_code, 403)
        other = User.objects.create_user(username='other_teacher', role=User.Role.TEACHER)
        Teacher.objects.create(user=other)
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get('/api/attempt_question/', {'attempt': self.attempt.id}).data['results'], [])

    def test_creator_owns_new_group(self):
        self.client.force_authenticate(self.teacher_user)
        response = self.client.post('/api/group/', {'name': 'Created'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Group.objects.get(pk=response.data['id']).teacher_id, self.teacher.id)

    def test_today_is_pending_and_full_correct_is_distinct_from_passing(self):
        from learning.views import GroupViewSet
        view = GroupViewSet()
        self.assertEqual(view._build_detailed_statistics_test(self.entry, None)['result'], 'not_started')
        self.question.is_active = False
        self.question.save()
        self.assertEqual(view._build_detailed_statistics_test(self.entry, None)['result'], 'not_ready')
        self.attempt.status = 'completed'
        self.attempt.is_success = True
        self.attempt.stats_correct_answers = 2
        self.attempt.stats_total_questions = 3
        cell = view._build_detailed_statistics_cell(self.entry.scheduled_for, [self.entry], {(self.student.id, self.entry.id): self.attempt}, self.student.id)
        self.assertEqual(cell['state'], 'partial')

    def test_preview_deduplication_and_undo_receipt(self):
        rows = [[SpreadsheetCell('Instruction', 'Instruction')], [SpreadsheetCell(x,x) for x in ['Imported question', 'Yes', 'No', 'Yes']]]
        def upload():
            return SimpleUploadedFile('questions.xlsx', b'fixture')
        with patch('learning.services.question_import._read_spreadsheet_rows', return_value=rows):
            count = self.task.questions.count()
            preview = import_batch(task=self.task, upload=upload(), user=self.teacher_user, preview=True)
            self.assertEqual(preview['imported_count'], 1)
            self.assertEqual(self.task.questions.count(), count)
            committed = import_batch(task=self.task, upload=upload(), user=self.teacher_user)
            repeated = import_batch(task=self.task, upload=upload(), user=self.teacher_user)
            self.assertEqual(repeated['imported_count'], 0)
            self.assertEqual(repeated['duplicate_count'], 1)
            self.assertEqual(undo_batch(task=self.task, user=self.teacher_user, token=committed['undo_token']), 1)
            self.assertEqual(self.task.questions.count(), count)

    def test_undo_refuses_changed_questions(self):
        from rest_framework.exceptions import ValidationError
        rows = [[SpreadsheetCell('Instruction', 'Instruction')], [SpreadsheetCell(x,x) for x in ['Imported', 'Yes', 'No', 'Yes']]]
        with patch('learning.services.question_import._read_spreadsheet_rows', return_value=rows):
            committed = import_batch(task=self.task, upload=SimpleUploadedFile('a.xlsx', b'x'), user=self.teacher_user)
        self.task.questions.filter(text='Imported').update(text='Edited')
        with self.assertRaises(ValidationError):
            undo_batch(task=self.task, user=self.teacher_user, token=committed['undo_token'])

    def test_autosave_retry_after_lost_response_updates_same_answer(self):
        payload = {'attempt_question': self.aq.id, 'selected_choices': [self.correct.id]}
        for _ in range(2):
            response = self.client.post('/api/answer/', payload, format='json')
            self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Answer.objects.filter(attempt_question=self.aq).count(), 1)

    def test_autosave_rechecks_status_after_validation(self):
        from types import SimpleNamespace
        from rest_framework.exceptions import ValidationError
        from learning.serializers import AnswerSerializer
        serializer = AnswerSerializer(data={'attempt_question': self.aq.id, 'selected_choices': [self.correct.id]},
            context={'request': SimpleNamespace(user=self.student_user)})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        Attempt.objects.filter(pk=self.attempt.pk).update(status='completed')
        with self.assertRaises(ValidationError):
            serializer.save()
        self.assertFalse(Answer.objects.filter(attempt_question=self.aq).exists())

    def test_not_ready_task_cannot_be_scheduled(self):
        GroupTeachingAssignment.objects.create(group=self.group, teacher=self.teacher, subject=self.subject,
                                               workbook=self.topic.unit.workbook)
        self.client.force_authenticate(self.teacher_user)
        self.question.is_active = False
        self.question.save()
        response = self.client.patch(f'/api/group/{self.group.id}/topic-calendar/',
                                     {'date': timezone.localdate().isoformat(), 'task': self.task.id}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data['code'], 'task_not_ready')

    def test_protected_schedule_keeps_assignment_on_failed_delete(self):
        assignment = GroupTeachingAssignment.objects.create(group=self.group, teacher=self.teacher,
            subject=self.subject, workbook=self.topic.unit.workbook)
        self.client.force_authenticate(self.teacher_user)
        response = self.client.delete(f'/api/group/{self.group.id}/teacher-assignment/')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(GroupTeachingAssignment.objects.filter(pk=assignment.pk).exists())
        self.assertTrue(GroupTopicSchedule.objects.filter(pk=self.entry.pk).exists())

    def test_downloadable_templates_are_importable_and_undoable(self):
        directory = Path(__file__).resolve().parent.parent / 'student-platform-frontend/public/templates'
        for kind in ['single_choice', 'multiple_choice', 'matching']:
            with self.subTest(kind=kind):
                template = directory / (kind + '.xlsx')
                response = self.client.get(f'/templates/{template.name}')
                self.assertEqual(response.status_code, 200)
                self.assertIn('attachment', response['Content-Disposition'])
                downloaded = b''.join(response.streaming_content)
                response.close()
                self.assertEqual(downloaded, template.read_bytes())
                result = import_batch(task=self.task, user=self.teacher_user,
                    upload=SimpleUploadedFile(template.name, downloaded), question_type=kind)
                self.assertEqual(result['imported_count'], 1)
                self.assertEqual(undo_batch(task=self.task, user=self.teacher_user, token=result['undo_token']), 1)
