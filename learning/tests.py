from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Student, Teacher, User
from learning.models import (
    Answer,
    Attempt,
    Choice,
    Group,
    GroupTopicSchedule,
    GroupTeachingAssignment,
    Question,
    Subject,
    Task,
    Topic,
    Unit,
    Workbook,
)
from learning.services.question_import import (
    SpreadsheetCell,
    _read_spreadsheet_rows,
    _render_rich_text_html,
    import_questions_from_xls,
)


class LearningApiTests(APITestCase):
    def setUp(self):
        self.auth_user = User.objects.create_user(
            username="teacher_api",
            password="StrongPass123",
            role=User.Role.TEACHER,
        )
        self.teacher = Teacher.objects.create(user=self.auth_user)
        self.client.force_authenticate(self.auth_user)

    def _create_question_with_two_choices(self, topic, text):
        question = Question.objects.create(
            topic=topic,
            text=text,
            question_type=Question.QuestionType.SINGLE_CHOICE,
            is_active=True,
        )
        Choice.objects.create(question=question, text="Correct", is_correct=True, order=1)
        Choice.objects.create(question=question, text="Wrong", is_correct=False, order=2)
        return question

    def _authenticate_student(self, username):
        student_user = User.objects.create_user(
            username=username,
            password="StrongPass123",
            role=User.Role.STUDENT,
        )
        student = Student.objects.create(user=student_user)
        self.client.force_authenticate(student_user)
        return student

    def _create_schedule_entry(self, student, topic, scheduled_for=None, group_name="Schedule Group"):
        group = Group.objects.create(name=group_name, is_active=True)
        group.students.add(student)
        return GroupTopicSchedule.objects.create(
            group=group,
            teacher=self.teacher,
            topic=topic,
            scheduled_for=scheduled_for or timezone.localdate(),
        )

    def test_create_question_with_choices(self):
        subject = Subject.objects.create(name="Mathematics")
        topic = Topic.objects.create(subject=subject, title="Math")
        old_timestamp = timezone.now() - timedelta(days=1)
        Topic.objects.filter(id=topic.id).update(updated_at=old_timestamp)
        payload = {
            "topic": topic.id,
            "text": "2 + 2 = ?",
            "question_type": "single_choice",
            "is_active": True,
            "choices": [
                {"text": "3", "is_correct": False, "order": 1},
                {"text": "4", "is_correct": True, "order": 2},
            ],
        }

        response = self.client.post("/api/question/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        question = Question.objects.get(topic=topic, text="2 + 2 = ?")
        self.assertEqual(question.choices.count(), 2)
        self.assertEqual(question.question_type, "single_choice")
        topic.refresh_from_db()
        self.assertGreater(topic.updated_at, old_timestamp)

        second_old_timestamp = timezone.now() - timedelta(hours=12)
        Topic.objects.filter(id=topic.id).update(updated_at=second_old_timestamp)
        delete_response = self.client.delete(f"/api/question/{question.id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        topic.refresh_from_db()
        self.assertGreater(topic.updated_at, second_old_timestamp)

    def test_group_find_and_add_student_by_user_id(self):
        group = Group.objects.create(name="Group A", teacher=self.teacher)
        old_timestamp = timezone.now() - timedelta(days=1)
        Group.objects.filter(id=group.id).update(updated_at=old_timestamp)
        student_user = User.objects.create_user(
            username="student1",
            password="StrongPass123",
            role=User.Role.STUDENT,
        )
        student = Student.objects.create(user=student_user)

        find_response = self.client.get(
            f"/api/group/{group.id}/find-student/", {"user_id": student_user.id}
        )
        self.assertEqual(find_response.status_code, status.HTTP_200_OK)
        self.assertFalse(find_response.data["in_group"])

        add_response = self.client.post(
            f"/api/group/{group.id}/add-student/",
            {"user_id": student_user.id},
            format="json",
        )
        self.assertEqual(add_response.status_code, status.HTTP_200_OK)
        self.assertTrue(add_response.data["added"])
        self.assertTrue(group.students.filter(id=student.id).exists())
        group.refresh_from_db()
        self.assertGreater(group.updated_at, old_timestamp)

        second_old_timestamp = timezone.now() - timedelta(hours=12)
        Group.objects.filter(id=group.id).update(updated_at=second_old_timestamp)
        remove_response = self.client.post(
            f"/api/group/{group.id}/remove-student/",
            {"user_id": student_user.id},
            format="json",
        )
        self.assertEqual(remove_response.status_code, status.HTTP_200_OK)
        self.assertTrue(remove_response.data["removed"])
        self.assertFalse(group.students.filter(id=student.id).exists())
        group.refresh_from_db()
        self.assertGreater(group.updated_at, second_old_timestamp)

    def test_group_search_students_by_username_and_user_id(self):
        group = Group.objects.create(name="Group Search", teacher=self.teacher)

        user_a = User.objects.create_user(
            username="alex_student",
            password="StrongPass123",
            role=User.Role.STUDENT,
        )
        student_a = Student.objects.create(user=user_a)

        user_b = User.objects.create_user(
            username="maria",
            password="StrongPass123",
            role=User.Role.STUDENT,
        )
        Student.objects.create(user=user_b)

        group.students.add(student_a)

        username_response = self.client.get(
            f"/api/group/{group.id}/search-students/", {"q": "alex"}
        )
        self.assertEqual(username_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(username_response.data), 1)
        self.assertEqual(username_response.data[0]["username"], "alex_student")
        self.assertTrue(username_response.data[0]["in_group"])

        id_response = self.client.get(
            f"/api/group/{group.id}/search-students/", {"q": str(user_b.id)}
        )
        self.assertEqual(id_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(id_response.data), 1)
        self.assertIn("maria", [item["username"] for item in id_response.data])

    def test_only_group_owner_teacher_can_manage_group_students(self):
        group = Group.objects.create(name="Locked Group", teacher=self.teacher)
        student_user = User.objects.create_user(
            username="group_member_student",
            password="StrongPass123",
            role=User.Role.STUDENT,
        )
        student = Student.objects.create(user=student_user)

        other_teacher_user = User.objects.create_user(
            username="other_group_teacher",
            password="StrongPass123",
            role=User.Role.TEACHER,
        )
        Teacher.objects.create(user=other_teacher_user)
        self.client.force_authenticate(other_teacher_user)

        find_response = self.client.get(
            f"/api/group/{group.id}/find-student/",
            {"user_id": student_user.id},
        )
        self.assertEqual(find_response.status_code, status.HTTP_403_FORBIDDEN)

        add_response = self.client.post(
            f"/api/group/{group.id}/add-student/",
            {"user_id": student_user.id},
            format="json",
        )
        self.assertEqual(add_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(group.students.filter(id=student.id).exists())

        search_response = self.client.get(
            f"/api/group/{group.id}/search-students/",
            {"q": "group_member"},
        )
        self.assertEqual(search_response.status_code, status.HTTP_403_FORBIDDEN)

        group.students.add(student)
        remove_response = self.client.post(
            f"/api/group/{group.id}/remove-student/",
            {"user_id": student_user.id},
            format="json",
        )
        self.assertEqual(remove_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(group.students.filter(id=student.id).exists())

    def test_student_cannot_access_teacher_crud_but_can_view_own_group_ranking(self):
        subject = Subject.objects.create(name="Permissions Subject")
        topic = Topic.objects.create(subject=subject, title="Permissions Topic")
        task = Task.objects.create(topic=topic, title="Protected Task")
        group = Group.objects.create(name="Permissions Group")

        student = self._authenticate_student("student_permissions")
        group.students.add(student)

        group_list_response = self.client.get("/api/group/")
        self.assertEqual(group_list_response.status_code, status.HTTP_403_FORBIDDEN)

        task_create_response = self.client.post(
            "/api/task/",
            {
                "topic": topic.id,
                "title": "Student cannot create this",
                "questions_per_attempt": 5,
                "passing_correct_answers": 3,
            },
            format="json",
        )
        self.assertEqual(task_create_response.status_code, status.HTTP_403_FORBIDDEN)

        question_create_response = self.client.post(
            "/api/question/",
            {
                "task": task.id,
                "text": "Forbidden question",
                "question_type": Question.QuestionType.SINGLE_CHOICE,
                "choices": [
                    {"text": "A", "is_correct": True, "order": 1},
                    {"text": "B", "is_correct": False, "order": 2},
                ],
            },
            format="json",
        )
        self.assertEqual(question_create_response.status_code, status.HTTP_403_FORBIDDEN)

        ranking_response = self.client.get(f"/api/group/{group.id}/ranking/")
        self.assertEqual(ranking_response.status_code, status.HTTP_200_OK)
        self.assertEqual(ranking_response.data["group_id"], group.id)
        self.assertEqual(ranking_response.data["rank"], 1)

    def test_topics_with_same_title_allowed_for_different_subjects(self):
        algebra = Subject.objects.create(name="Algebra")
        geometry = Subject.objects.create(name="Geometry")

        Topic.objects.create(subject=algebra, title="Introduction")
        Topic.objects.create(subject=geometry, title="Introduction")

        with self.assertRaises(IntegrityError):
            Topic.objects.create(subject=algebra, title="Introduction")

    def test_workbook_unit_topic_hierarchy_api(self):
        subject = Subject.objects.create(name="English")

        workbook_response = self.client.post(
            "/api/workbook/",
            {
                "subject": subject.id,
                "title": "Workbook A",
                "description": "Practice workbook",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(workbook_response.status_code, status.HTTP_201_CREATED)
        workbook_id = workbook_response.data["id"]

        unit_response = self.client.post(
            "/api/unit/",
            {
                "workbook": workbook_id,
                "title": "Unit 1",
                "description": "Basics",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(unit_response.status_code, status.HTTP_201_CREATED)
        unit_id = unit_response.data["id"]
        self.assertEqual(unit_response.data["subject"], subject.id)

        topic_response = self.client.post(
            "/api/topic/",
            {
                "unit": unit_id,
                "title": "Present simple",
                "description": "Grammar practice",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(topic_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(topic_response.data["subject"], subject.id)
        self.assertEqual(topic_response.data["workbook"], workbook_id)
        self.assertEqual(topic_response.data["unit"], unit_id)

        topic = Topic.objects.get(id=topic_response.data["id"])
        self.assertEqual(topic.subject_id, subject.id)
        self.assertEqual(topic.unit_id, unit_id)

    def test_topic_create_with_subject_only_uses_default_unit(self):
        subject = Subject.objects.create(name="History")

        response = self.client.post(
            "/api/topic/",
            {
                "subject": subject.id,
                "title": "Ancient world",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        topic = Topic.objects.get(id=response.data["id"])
        self.assertEqual(topic.subject_id, subject.id)
        self.assertEqual(topic.unit.title, Topic.DEFAULT_UNIT_TITLE)
        self.assertEqual(topic.unit.workbook.title, Topic.DEFAULT_WORKBOOK_TITLE)
        self.assertEqual(
            Workbook.objects.filter(subject=subject, title=Topic.DEFAULT_WORKBOOK_TITLE).count(),
            1,
        )
        self.assertEqual(Unit.objects.filter(workbook=topic.unit.workbook).count(), 1)

    def test_topic_create_requires_unit_when_subject_already_has_workbook_hierarchy(self):
        subject = Subject.objects.create(name="Geography")
        workbook = Workbook.objects.create(subject=subject, title="Atlas")
        unit = Unit.objects.create(workbook=workbook, title="Europe")

        response = self.client.post(
            "/api/topic/",
            {
                "subject": subject.id,
                "title": "Capitals",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("unit", response.data)

        valid_response = self.client.post(
            "/api/topic/",
            {
                "subject": subject.id,
                "unit": unit.id,
                "title": "Capitals",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(valid_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(valid_response.data["workbook"], workbook.id)
        self.assertEqual(valid_response.data["unit"], unit.id)

    def test_topic_rejects_subject_unit_mismatch(self):
        math = Subject.objects.create(name="Math hierarchy")
        physics = Subject.objects.create(name="Physics hierarchy")
        workbook = Workbook.objects.create(subject=math, title="Math Workbook")
        unit = Unit.objects.create(workbook=workbook, title="Algebra Unit")

        response = self.client.post(
            "/api/topic/",
            {
                "subject": physics.id,
                "unit": unit.id,
                "title": "Linear equations",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("unit", response.data)

    def test_group_teacher_assignment_validation(self):
        math = Subject.objects.create(name="Math")
        physics = Subject.objects.create(name="Physics")

        math_topic = Topic.objects.create(subject=math, title="Linear equations")
        physics_topic = Topic.objects.create(subject=physics, title="Kinematics")
        group = Group.objects.create(name="Group Subject Topic")

        topic_only_response = self.client.patch(
            f"/api/group/{group.id}/teacher-assignment/",
            {"topic": math_topic.id},
            format="json",
        )
        self.assertEqual(topic_only_response.status_code, status.HTTP_400_BAD_REQUEST)

        mismatch_response = self.client.patch(
            f"/api/group/{group.id}/teacher-assignment/",
            {"subject": math.id, "topic": physics_topic.id},
            format="json",
        )
        self.assertEqual(mismatch_response.status_code, status.HTTP_400_BAD_REQUEST)

        valid_response = self.client.patch(
            f"/api/group/{group.id}/teacher-assignment/",
            {"subject": math.id, "topic": math_topic.id},
            format="json",
        )
        self.assertEqual(valid_response.status_code, status.HTTP_201_CREATED)

        assignment = GroupTeachingAssignment.objects.get(group=group, teacher__user=self.auth_user)
        self.assertEqual(assignment.subject_id, math.id)
        self.assertEqual(assignment.topic_id, math_topic.id)

    def test_group_teacher_assignments_are_isolated_per_teacher(self):
        teacher_user_2 = User.objects.create_user(
            username="teacher_api_2",
            password="StrongPass123",
            role=User.Role.TEACHER,
        )
        Teacher.objects.create(user=teacher_user_2)

        group = Group.objects.create(name="Shared Group")
        algebra = Subject.objects.create(name="Algebra")
        chemistry = Subject.objects.create(name="Chemistry")
        algebra_topic = Topic.objects.create(subject=algebra, title="Fractions")
        chemistry_topic = Topic.objects.create(subject=chemistry, title="Acids")

        response_teacher_1 = self.client.patch(
            f"/api/group/{group.id}/teacher-assignment/",
            {"subject": algebra.id, "topic": algebra_topic.id},
            format="json",
        )
        self.assertEqual(response_teacher_1.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(teacher_user_2)
        response_teacher_2 = self.client.patch(
            f"/api/group/{group.id}/teacher-assignment/",
            {"subject": chemistry.id, "topic": chemistry_topic.id},
            format="json",
        )
        self.assertEqual(response_teacher_2.status_code, status.HTTP_201_CREATED)

        read_teacher_2 = self.client.get(f"/api/group/{group.id}/teacher-assignment/")
        self.assertEqual(read_teacher_2.status_code, status.HTTP_200_OK)
        self.assertEqual(read_teacher_2.data["subject"], chemistry.id)
        self.assertEqual(read_teacher_2.data["topic"], chemistry_topic.id)

        self.client.force_authenticate(self.auth_user)
        read_teacher_1 = self.client.get(f"/api/group/{group.id}/teacher-assignment/")
        self.assertEqual(read_teacher_1.status_code, status.HTTP_200_OK)
        self.assertEqual(read_teacher_1.data["subject"], algebra.id)
        self.assertEqual(read_teacher_1.data["topic"], algebra_topic.id)

    def test_group_topic_calendar_save_and_list_entries(self):
        group = Group.objects.create(name="Schedule Group")
        subject = Subject.objects.create(name="Literature")
        topic_a = Topic.objects.create(subject=subject, title="Poetry")
        topic_b = Topic.objects.create(subject=subject, title="Drama")

        assignment_response = self.client.patch(
            f"/api/group/{group.id}/teacher-assignment/",
            {"subject": subject.id, "topic": topic_a.id},
            format="json",
        )
        self.assertEqual(assignment_response.status_code, status.HTTP_201_CREATED)

        save_response = self.client.patch(
            f"/api/group/{group.id}/topic-calendar/",
            {"date": "2026-05-11", "topic": topic_b.id},
            format="json",
        )
        self.assertEqual(save_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(save_response.data["topic"], topic_b.id)
        self.assertEqual(save_response.data["subject"], subject.id)

        list_response = self.client.get(
            f"/api/group/{group.id}/topic-calendar/",
            {"start_date": "2026-05-11", "days": 3},
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["assignment_subject"], subject.id)
        self.assertEqual(len(list_response.data["results"]), 3)
        self.assertEqual(list_response.data["results"][0]["date"], "2026-05-11")
        self.assertEqual(list_response.data["results"][0]["topic"], topic_b.id)
        self.assertIsNone(list_response.data["results"][1]["topic"])

    def test_group_topic_calendar_requires_saved_subject(self):
        group = Group.objects.create(name="Unbound Schedule Group")
        subject = Subject.objects.create(name="History")
        topic = Topic.objects.create(subject=subject, title="Ancient Rome")

        response = self.client.patch(
            f"/api/group/{group.id}/topic-calendar/",
            {"date": "2026-05-11", "topic": topic.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_group_topic_calendar_is_cleared_when_assignment_subject_changes(self):
        group = Group.objects.create(name="Schedule Reset Group")
        algebra = Subject.objects.create(name="Algebra Schedule")
        geometry = Subject.objects.create(name="Geometry Schedule")
        algebra_topic = Topic.objects.create(subject=algebra, title="Fractions")
        geometry_topic = Topic.objects.create(subject=geometry, title="Triangles")

        self.client.patch(
            f"/api/group/{group.id}/teacher-assignment/",
            {"subject": algebra.id, "topic": algebra_topic.id},
            format="json",
        )
        self.client.patch(
            f"/api/group/{group.id}/topic-calendar/",
            {"date": "2026-05-11", "topic": algebra_topic.id},
            format="json",
        )

        self.assertEqual(
            GroupTopicSchedule.objects.filter(group=group, teacher__user=self.auth_user).count(),
            1,
        )

        update_response = self.client.patch(
            f"/api/group/{group.id}/teacher-assignment/",
            {"subject": geometry.id, "topic": geometry_topic.id},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            GroupTopicSchedule.objects.filter(group=group, teacher__user=self.auth_user).exists()
        )

    def test_group_topic_calendar_delete_attempt_check_is_scoped_to_group_entry(self):
        subject = Subject.objects.create(name="Scoped Attempts")
        topic = Topic.objects.create(subject=subject, title="Shared Topic")
        task = Task.get_default_for_topic(topic)
        group_with_attempt = Group.objects.create(name="Group With Attempt")
        group_without_attempt = Group.objects.create(name="Group Without Attempt")
        student_user = User.objects.create_user(
            username="student_scoped_attempt",
            password="StrongPass123",
            role=User.Role.STUDENT,
        )
        student = Student.objects.create(user=student_user)
        group_with_attempt.students.add(student)

        schedule_with_attempt = GroupTopicSchedule.objects.create(
            group=group_with_attempt,
            teacher=self.teacher,
            scheduled_for="2026-05-11",
            task=task,
        )
        schedule_without_attempt = GroupTopicSchedule.objects.create(
            group=group_without_attempt,
            teacher=self.teacher,
            scheduled_for="2026-05-11",
            task=task,
        )
        Attempt.objects.create(
            student=student,
            topic=topic,
            task=task,
            schedule_entry=schedule_with_attempt,
        )

        delete_available_response = self.client.delete(
            f"/api/group/{group_without_attempt.id}/topic-calendar/",
            {"schedule_entry": schedule_without_attempt.id},
        )

        self.assertEqual(delete_available_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            GroupTopicSchedule.objects.filter(id=schedule_without_attempt.id).exists()
        )
        self.assertTrue(
            GroupTopicSchedule.objects.filter(id=schedule_with_attempt.id).exists()
        )

        delete_blocked_response = self.client.delete(
            f"/api/group/{group_with_attempt.id}/topic-calendar/",
            {"schedule_entry": schedule_with_attempt.id},
        )

        self.assertEqual(delete_blocked_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(
            GroupTopicSchedule.objects.filter(id=schedule_with_attempt.id).exists()
        )

    def test_task_import_questions_api_uses_uploaded_file(self):
        subject = Subject.objects.create(name="Task Import API")
        topic = Topic.objects.create(subject=subject, title="Task Import Topic")
        task = Task.objects.create(topic=topic, title="Task Import Pool")
        uploaded_file = SimpleUploadedFile(
            "questions.xlsx",
            b"fake spreadsheet bytes",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        with TemporaryDirectory() as temp_dir:
            with self.settings(MEDIA_ROOT=temp_dir):
                with patch("learning.views.import_questions_from_xls", return_value=[]) as import_mock:
                    response = self.client.post(
                        f"/api/task/{task.id}/import-questions/",
                        {"src": uploaded_file, "is_active": "false"},
                        format="multipart",
                    )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task.refresh_from_db()
        self.assertEqual(response.data["imported_count"], 0)
        self.assertTrue(task.src.name.endswith(".xlsx"))
        import_mock.assert_called_once()
        _, kwargs = import_mock.call_args
        self.assertEqual(kwargs["task"].id, task.id)
        self.assertEqual(kwargs["src"].name, task.src.name)
        self.assertFalse(kwargs["is_active"])

    def test_create_task_accepts_attempt_settings(self):
        subject = Subject.objects.create(name="Task Settings API")
        topic = Topic.objects.create(subject=subject, title="Task Settings Topic")

        response = self.client.post(
            "/api/task/",
            {
                "topic": topic.id,
                "title": "Short quiz",
                "questions_per_attempt": 5,
                "passing_correct_answers": 3,
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["questions_per_attempt"], 5)
        self.assertEqual(response.data["passing_correct_answers"], 3)
        task = Task.objects.get(id=response.data["id"])
        self.assertEqual(task.questions_per_attempt, 5)
        self.assertEqual(task.passing_correct_answers, 3)

    def test_create_task_rejects_passing_threshold_above_question_count(self):
        subject = Subject.objects.create(name="Task Settings Validation")
        topic = Topic.objects.create(subject=subject, title="Task Settings Validation Topic")

        response = self.client.post(
            "/api/task/",
            {
                "topic": topic.id,
                "title": "Impossible quiz",
                "questions_per_attempt": 5,
                "passing_correct_answers": 6,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("passing_correct_answers", response.data)

    def test_student_create_attempt_generates_10_random_questions(self):
        student = self._authenticate_student("student_attempt_1")
        subject = Subject.objects.create(name="Biology")
        topic = Topic.objects.create(subject=subject, title="Cells", is_active=True)
        schedule_entry = self._create_schedule_entry(
            student,
            topic,
            group_name="Biology Schedule Group",
        )

        for index in range(12):
            self._create_question_with_two_choices(topic, f"Question #{index + 1}")

        response = self.client.post(
            "/api/attempt/",
            {"schedule_entry": schedule_entry.id, "subject": subject.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        attempt = Attempt.objects.get(id=response.data["id"])
        self.assertEqual(attempt.student_id, student.id)
        self.assertEqual(attempt.schedule_entry_id, schedule_entry.id)
        self.assertEqual(attempt.attempt_questions.count(), 10)
        self.assertEqual(
            list(attempt.attempt_questions.order_by("order").values_list("order", flat=True)),
            list(range(1, 11)),
        )

    def test_student_create_attempt_uses_task_question_count(self):
        student = self._authenticate_student("student_attempt_custom_count")
        subject = Subject.objects.create(name="Custom Count Subject")
        topic = Topic.objects.create(
            subject=subject,
            title="Custom Count Topic",
            is_active=True,
        )
        task = Task.objects.create(
            topic=topic,
            title="Five question quiz",
            questions_per_attempt=5,
            passing_correct_answers=3,
        )
        schedule_entry = GroupTopicSchedule.objects.create(
            group=Group.objects.create(name="Custom Count Group", is_active=True),
            teacher=self.teacher,
            task=task,
            scheduled_for=timezone.localdate(),
        )
        schedule_entry.group.students.add(student)

        for index in range(7):
            question = Question.objects.create(
                topic=topic,
                task=task,
                text=f"Custom count question #{index + 1}",
                question_type=Question.QuestionType.SINGLE_CHOICE,
                is_active=True,
            )
            Choice.objects.create(question=question, text="Correct", is_correct=True, order=1)
            Choice.objects.create(question=question, text="Wrong", is_correct=False, order=2)

        response = self.client.post(
            "/api/attempt/",
            {"schedule_entry": schedule_entry.id, "subject": subject.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        attempt = Attempt.objects.get(id=response.data["id"])
        self.assertEqual(attempt.attempt_questions.count(), 5)
        self.assertEqual(response.data["passing_correct_answers"], 3)

    def test_student_create_attempt_uses_scheduled_task_question_pool(self):
        student = self._authenticate_student("student_attempt_task_pool")
        subject = Subject.objects.create(name="Task Pool Subject")
        topic = Topic.objects.create(
            subject=subject,
            title="Task Pool Topic",
            is_active=True,
        )
        scheduled_task = Task.objects.create(topic=topic, title="Scheduled task")
        self._create_schedule_entry(
            student,
            topic,
            group_name="Default Pool Group",
        )
        schedule_entry = GroupTopicSchedule.objects.create(
            group=Group.objects.create(name="Task Pool Group", is_active=True),
            teacher=self.teacher,
            task=scheduled_task,
            scheduled_for=timezone.localdate(),
        )
        schedule_entry.group.students.add(student)

        for index in range(12):
            self._create_question_with_two_choices(
                topic,
                f"Default pool question #{index + 1}",
            )

        response = self.client.post(
            "/api/attempt/",
            {"schedule_entry": schedule_entry.id, "subject": subject.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("task", response.data)

    def test_finish_attempt_calculates_correct_and_wrong_answers(self):
        student = self._authenticate_student("student_attempt_2")
        subject = Subject.objects.create(name="Physics")
        topic = Topic.objects.create(subject=subject, title="Mechanics", is_active=True)
        schedule_entry = self._create_schedule_entry(
            student,
            topic,
            group_name="Physics Schedule Group",
        )

        for index in range(10):
            self._create_question_with_two_choices(topic, f"Q{index + 1}")

        start_response = self.client.post(
            "/api/attempt/",
            {"schedule_entry": schedule_entry.id, "subject": subject.id},
            format="json",
        )
        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)
        attempt_id = start_response.data["id"]
        attempt = Attempt.objects.get(id=attempt_id)

        attempt_questions = list(attempt.attempt_questions.select_related("question"))
        for attempt_question in attempt_questions[:3]:
            correct_choice = attempt_question.question.choices.get(is_correct=True)
            answer_response = self.client.post(
                "/api/answer/",
                {
                    "attempt_question": attempt_question.id,
                    "selected_choices": [correct_choice.id],
                },
                format="json",
            )
            self.assertEqual(answer_response.status_code, status.HTTP_201_CREATED)

        for attempt_question in attempt_questions[3:5]:
            wrong_choice = attempt_question.question.choices.get(is_correct=False)
            answer_response = self.client.post(
                "/api/answer/",
                {
                    "attempt_question": attempt_question.id,
                    "selected_choices": [wrong_choice.id],
                },
                format="json",
            )
            self.assertEqual(answer_response.status_code, status.HTTP_201_CREATED)

        finish_response = self.client.patch(
            f"/api/attempt/{attempt_id}/",
            {"status": Attempt.Status.COMPLETED},
            format="json",
        )
        self.assertEqual(finish_response.status_code, status.HTTP_200_OK)
        self.assertEqual(finish_response.data["correct_count"], 3)
        self.assertEqual(finish_response.data["wrong_count"], 7)
        self.assertEqual(finish_response.data["total_questions"], 10)

        attempt.refresh_from_db()
        self.assertEqual(attempt.status, Attempt.Status.COMPLETED)
        self.assertIsNotNone(attempt.finished_at)
        self.assertEqual(Answer.objects.filter(attempt_question__attempt=attempt).count(), 10)
        self.assertEqual(
            Answer.objects.filter(attempt_question__attempt=attempt, is_correct=True).count(),
            3,
        )
        self.assertEqual(
            Answer.objects.filter(attempt_question__attempt=attempt, is_correct=False).count(),
            7,
        )

    def test_finish_attempt_uses_task_passing_threshold(self):
        student = self._authenticate_student("student_attempt_custom_pass")
        subject = Subject.objects.create(name="Custom Pass Subject")
        topic = Topic.objects.create(
            subject=subject,
            title="Custom Pass Topic",
            is_active=True,
        )
        task = Task.objects.create(
            topic=topic,
            title="Pass from three",
            questions_per_attempt=5,
            passing_correct_answers=3,
        )
        schedule_entry = GroupTopicSchedule.objects.create(
            group=Group.objects.create(name="Custom Pass Group", is_active=True),
            teacher=self.teacher,
            task=task,
            scheduled_for=timezone.localdate(),
        )
        schedule_entry.group.students.add(student)

        for index in range(5):
            question = Question.objects.create(
                topic=topic,
                task=task,
                text=f"Custom pass question #{index + 1}",
                question_type=Question.QuestionType.SINGLE_CHOICE,
                is_active=True,
            )
            Choice.objects.create(question=question, text="Correct", is_correct=True, order=1)
            Choice.objects.create(question=question, text="Wrong", is_correct=False, order=2)

        start_response = self.client.post(
            "/api/attempt/",
            {"schedule_entry": schedule_entry.id, "subject": subject.id},
            format="json",
        )
        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)
        attempt = Attempt.objects.get(id=start_response.data["id"])

        attempt_questions = list(attempt.attempt_questions.select_related("question"))
        for attempt_question in attempt_questions[:3]:
            correct_choice = attempt_question.question.choices.get(is_correct=True)
            self.client.post(
                "/api/answer/",
                {
                    "attempt_question": attempt_question.id,
                    "selected_choices": [correct_choice.id],
                },
                format="json",
            )

        finish_response = self.client.patch(
            f"/api/attempt/{attempt.id}/",
            {"status": Attempt.Status.COMPLETED},
            format="json",
        )

        self.assertEqual(finish_response.status_code, status.HTTP_200_OK)
        self.assertEqual(finish_response.data["correct_count"], 3)
        self.assertEqual(finish_response.data["passing_correct_answers"], 3)
        self.assertEqual(finish_response.data["result_outcome"], "success")
        attempt.refresh_from_db()
        self.assertTrue(attempt.is_success)

    def test_student_cannot_submit_answer_for_foreign_attempt(self):
        subject = Subject.objects.create(name="Chemistry")
        topic = Topic.objects.create(subject=subject, title="Atoms", is_active=True)
        for index in range(10):
            self._create_question_with_two_choices(topic, f"Chem Q{index + 1}")

        owner_student = self._authenticate_student("student_attempt_owner")
        schedule_entry = self._create_schedule_entry(
            owner_student,
            topic,
            group_name="Chemistry Schedule Group",
        )
        start_response = self.client.post(
            "/api/attempt/",
            {"schedule_entry": schedule_entry.id, "subject": subject.id},
            format="json",
        )
        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)
        attempt = Attempt.objects.get(id=start_response.data["id"])
        foreign_attempt_question = attempt.attempt_questions.first()

        student_two_user = User.objects.create_user(
            username="student_attempt_other",
            password="StrongPass123",
            role=User.Role.STUDENT,
        )
        Student.objects.create(user=student_two_user)
        self.client.force_authenticate(student_two_user)

        correct_choice = foreign_attempt_question.question.choices.get(is_correct=True)
        response = self.client.post(
            "/api/answer/",
            {
                "attempt_question": foreign_attempt_question.id,
                "selected_choices": [correct_choice.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("attempt_question", response.data)

    def test_student_cannot_start_second_attempt_for_same_schedule(self):
        student = self._authenticate_student("student_attempt_once")
        subject = Subject.objects.create(name="Geography")
        topic = Topic.objects.create(subject=subject, title="Maps", is_active=True)
        schedule_entry = self._create_schedule_entry(
            student,
            topic,
            group_name="Geography Schedule Group",
        )

        for index in range(10):
            self._create_question_with_two_choices(topic, f"Map Q{index + 1}")

        first_response = self.client.post(
            "/api/attempt/",
            {"schedule_entry": schedule_entry.id, "subject": subject.id},
            format="json",
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        second_response = self.client.post(
            "/api/attempt/",
            {"schedule_entry": schedule_entry.id, "subject": subject.id},
            format="json",
        )
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", second_response.data)

    def test_student_cannot_start_future_or_past_schedule_attempt(self):
        student = self._authenticate_student("student_attempt_date_limits")
        subject = Subject.objects.create(name="History Limits")
        topic = Topic.objects.create(subject=subject, title="World War II", is_active=True)

        for index in range(10):
            self._create_question_with_two_choices(topic, f"History Q{index + 1}")

        future_schedule = self._create_schedule_entry(
            student,
            topic,
            scheduled_for=timezone.localdate() + timedelta(days=1),
            group_name="Future Schedule Group",
        )
        past_schedule = self._create_schedule_entry(
            student,
            topic,
            scheduled_for=timezone.localdate() - timedelta(days=1),
            group_name="Past Schedule Group",
        )

        future_response = self.client.post(
            "/api/attempt/",
            {"schedule_entry": future_schedule.id, "subject": subject.id},
            format="json",
        )
        self.assertEqual(future_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", future_response.data)

        past_response = self.client.post(
            "/api/attempt/",
            {"schedule_entry": past_schedule.id, "subject": subject.id},
            format="json",
        )
        self.assertEqual(past_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", past_response.data)

    def test_student_cannot_finish_attempt_after_scheduled_day(self):
        student = self._authenticate_student("student_attempt_expired")
        subject = Subject.objects.create(name="Economics")
        topic = Topic.objects.create(subject=subject, title="Inflation", is_active=True)
        schedule_entry = self._create_schedule_entry(
            student,
            topic,
            scheduled_for=timezone.localdate(),
            group_name="Economics Schedule Group",
        )

        for index in range(10):
            self._create_question_with_two_choices(topic, f"Eco Q{index + 1}")

        start_response = self.client.post(
            "/api/attempt/",
            {"schedule_entry": schedule_entry.id, "subject": subject.id},
            format="json",
        )
        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)
        attempt_id = start_response.data["id"]

        with patch("learning.serializers.timezone.localdate", return_value=timezone.localdate() + timedelta(days=1)):
            finish_response = self.client.patch(
                f"/api/attempt/{attempt_id}/",
                {"status": Attempt.Status.COMPLETED},
                format="json",
            )

        self.assertEqual(finish_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", finish_response.data)


class QuestionImportTests(APITestCase):
    def _write_minimal_xlsx(self, path):
        shared_strings = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="12" uniqueCount="8">
  <si><t>Choose adj or adv:</t></si>
  <si><t>option 1</t></si>
  <si><t>option 2</t></si>
  <si><t>key</t></si>
  <si><r><t>I had a </t></r><r><rPr><b/></rPr><t>bad</t></r><r><t> day.</t></r></si>
  <si><t>adj</t></si>
  <si><t>adv</t></si>
  <si><t>My students study well.</t></si>
</sst>
"""
        sheet = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c><c r="D1" t="s"><v>3</v></c></row>
    <row r="2"><c r="A2" t="s"><v>4</v></c><c r="B2" t="s"><v>5</v></c><c r="C2" t="s"><v>6</v></c><c r="D2" t="s"><v>5</v></c></row>
    <row r="3"><c r="A3" t="s"><v>7</v></c><c r="B3" t="s"><v>5</v></c><c r="C3" t="s"><v>6</v></c><c r="D3" t="s"><v>6</v></c></row>
  </sheetData>
</worksheet>
"""
        with ZipFile(path, "w") as archive:
            archive.writestr("xl/sharedStrings.xml", shared_strings)
            archive.writestr("xl/worksheets/sheet1.xml", sheet)

    def test_import_from_xls_creates_single_choice_questions(self):
        subject = Subject.objects.create(name="English")
        topic = Topic.objects.create(subject=subject, title="Adjectives and adverbs")
        spreadsheet_rows = [
            [
                SpreadsheetCell(
                    "Choose adj (adjective) or adv (adverb):",
                    "Choose adj (adjective) or adv (adverb):",
                ),
                SpreadsheetCell("option 1", "<strong>option 1</strong>"),
                SpreadsheetCell("option 2", "<strong>option 2</strong>"),
                SpreadsheetCell("key", "<strong>key</strong>"),
            ],
            [
                SpreadsheetCell(
                    "I had a bad day yesterday.",
                    "I had a <strong>bad</strong> day yesterday.",
                ),
                SpreadsheetCell("adj", "adj"),
                SpreadsheetCell("adv", "adv"),
                SpreadsheetCell("adj", "adj"),
            ],
            [
                SpreadsheetCell(
                    "My students study well.",
                    "My students study <strong>well</strong>.",
                ),
                SpreadsheetCell("adj", "adj"),
                SpreadsheetCell("adv", "adv"),
                SpreadsheetCell("adv", "adv"),
            ],
        ]

        with patch(
            "learning.services.question_import._read_spreadsheet_rows",
            return_value=spreadsheet_rows,
        ):
            questions = import_questions_from_xls(topic=topic, src="1.xls")

        self.assertEqual(len(questions), 2)
        first_question = questions[0]
        self.assertEqual(
            first_question.instruction,
            "Choose adj (adjective) or adv (adverb):",
        )
        self.assertEqual(
            first_question.text,
            "I had a <strong>bad</strong> day yesterday.",
        )
        self.assertEqual(first_question.question_type, Question.QuestionType.SINGLE_CHOICE)
        self.assertEqual(first_question.choices.count(), 2)
        self.assertEqual(
            list(first_question.choices.values_list("text", "is_correct", "order")),
            [("adj", True, 1), ("adv", False, 2)],
        )

    def test_read_xlsx_rows_supports_shared_strings_and_rich_text(self):
        with TemporaryDirectory() as temp_dir:
            src_path = Path(temp_dir) / "questions.xlsx"
            self._write_minimal_xlsx(src_path)

            rows = _read_spreadsheet_rows(src_path)

        self.assertEqual(rows[0][0].plain, "Choose adj or adv:")
        self.assertEqual(rows[1][0].plain, "I had a bad day.")
        self.assertEqual(rows[1][0].html, "I had a <strong>bad</strong> day.")

    def test_import_from_xlsx_creates_questions_for_task(self):
        subject = Subject.objects.create(name="English XLSX")
        topic = Topic.objects.create(subject=subject, title="Adjectives XLSX")
        task = Task.objects.create(topic=topic, title="Task XLSX")

        with TemporaryDirectory() as temp_dir:
            src_path = Path(temp_dir) / "questions.xlsx"
            self._write_minimal_xlsx(src_path)

            questions = import_questions_from_xls(task=task, src=src_path)

        self.assertEqual(len(questions), 2)
        self.assertTrue(Question.objects.filter(task=task).exists())
        self.assertFalse(Question.objects.filter(task__isnull=True).exists())

    def test_import_creates_all_answer_options_from_row(self):
        subject = Subject.objects.create(name="English many options")
        topic = Topic.objects.create(subject=subject, title="Verb practice")
        spreadsheet_rows = [
            [
                SpreadsheetCell("Complete the sentence", "Complete the sentence"),
                SpreadsheetCell("Option 1", "Option 1"),
                SpreadsheetCell("Option 2", "Option 2"),
                SpreadsheetCell("Option 3", "Option 3"),
                SpreadsheetCell("Option 4", "Option 4"),
                SpreadsheetCell("Option 5", "Option 5"),
                SpreadsheetCell("Option 6", "Option 6"),
                SpreadsheetCell("Option 7", "Option 7"),
                SpreadsheetCell("Option 8", "Option 8"),
                SpreadsheetCell("Key", "Key"),
            ],
            [
                SpreadsheetCell(
                    "Students __________ to speak English well.",
                    "Students __________ to speak English well.",
                ),
                SpreadsheetCell("want", "want"),
                SpreadsheetCell("plan", "plan"),
                SpreadsheetCell("need", "need"),
                SpreadsheetCell("decide", "decide"),
                SpreadsheetCell("hope", "hope"),
                SpreadsheetCell("promise", "promise"),
                SpreadsheetCell("learn", "learn"),
                SpreadsheetCell("try", "try"),
                SpreadsheetCell("want", "want"),
            ],
        ]

        with patch(
            "learning.services.question_import._read_spreadsheet_rows",
            return_value=spreadsheet_rows,
        ):
            questions = import_questions_from_xls(topic=topic, src="many-options.xlsx")

        self.assertEqual(len(questions), 1)
        self.assertEqual(
            list(questions[0].choices.values_list("text", "is_correct", "order")),
            [
                ("want", True, 1),
                ("plan", False, 2),
                ("need", False, 3),
                ("decide", False, 4),
                ("hope", False, 5),
                ("promise", False, 6),
                ("learn", False, 7),
                ("try", False, 8),
            ],
        )

    def test_import_from_xls_rejects_rows_without_matching_answer_key(self):
        subject = Subject.objects.create(name="English grammar")
        topic = Topic.objects.create(subject=subject, title="Parts of speech")
        spreadsheet_rows = [
            [
                SpreadsheetCell(
                    "Choose adj (adjective) or adv (adverb):",
                    "Choose adj (adjective) or adv (adverb):",
                ),
                SpreadsheetCell("option 1", "option 1"),
                SpreadsheetCell("option 2", "option 2"),
                SpreadsheetCell("key", "key"),
            ],
            [
                SpreadsheetCell(
                    "This road is very dangerous.",
                    "This road is very <strong>dangerous</strong>.",
                ),
                SpreadsheetCell("adj", "adj"),
                SpreadsheetCell("adv", "adv"),
                SpreadsheetCell("noun", "noun"),
            ],
        ]

        with patch(
            "learning.services.question_import._read_spreadsheet_rows",
            return_value=spreadsheet_rows,
        ):
            with self.assertRaises(ValidationError):
                import_questions_from_xls(topic=topic, src="1.xls")

        self.assertEqual(Question.objects.count(), 0)
        self.assertEqual(Choice.objects.count(), 0)

    def test_render_rich_text_html_wraps_bold_runs(self):
        class Font:
            def __init__(self, weight):
                self.weight = weight
                self.bold = 0

        class Workbook:
            font_list = [Font(400), Font(700)]

        html = _render_rich_text_html(
            plain_text="Hello world!",
            runlist=[(0, 0), (6, 1)],
            workbook=Workbook(),
        )

        self.assertEqual(html, "Hello <strong>world!</strong>")


class TopicAdminImportTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="StrongPass123",
        )
        self.client.force_login(self.admin_user)
        self.subject = Subject.objects.create(name="English Admin")
        self.topic = Topic.objects.create(subject=self.subject, title="Grammar")

    def test_import_button_uses_attached_file(self):
        self.topic.src = "imports/1.xls"
        self.topic.save(update_fields=["src"])

        with patch("learning.admin.import_questions_from_xls", return_value=[]) as import_mock:
            response = self.client.post(
                reverse("admin:learning_topic_import_from_src", args=[self.topic.pk]),
                follow=True,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        import_mock.assert_called_once_with(
            topic=self.topic,
            src=self.topic.src,
            is_active=self.topic.is_active,
        )

    def test_import_button_requires_attached_file(self):
        with patch("learning.admin.import_questions_from_xls") as import_mock:
            response = self.client.post(
                reverse("admin:learning_topic_import_from_src", args=[self.topic.pk]),
                follow=True,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        import_mock.assert_not_called()
        self.assertContains(
            response,
            "Attach a .xls or .xlsx file to the topic before running import.",
        )

    def test_task_import_button_uses_attached_file(self):
        task = Task.objects.create(topic=self.topic, title="Admin task import")
        task.src = "imports/1.xlsx"
        task.save(update_fields=["src"])

        with patch("learning.admin.import_questions_from_xls", return_value=[]) as import_mock:
            response = self.client.post(
                reverse("admin:learning_task_import_from_src", args=[task.pk]),
                follow=True,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        import_mock.assert_called_once_with(
            task=task,
            src=task.src,
            is_active=task.is_active,
        )
