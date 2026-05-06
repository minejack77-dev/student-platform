from datetime import timedelta
from unittest.mock import patch

from django.db import IntegrityError
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
    Topic,
    Unit,
    Workbook,
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
        group = Group.objects.create(name="Group A")
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
        group = Group.objects.create(name="Group Search")

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
