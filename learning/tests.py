from datetime import timedelta

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
    GroupTeachingAssignment,
    Question,
    Subject,
    Topic,
)


class LearningApiTests(APITestCase):
    def setUp(self):
        self.auth_user = User.objects.create_user(
            username="teacher_api",
            password="StrongPass123",
            role=User.Role.TEACHER,
        )
        Teacher.objects.create(user=self.auth_user)
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

    def test_student_create_attempt_generates_10_random_questions(self):
        student = self._authenticate_student("student_attempt_1")
        subject = Subject.objects.create(name="Biology")
        topic = Topic.objects.create(subject=subject, title="Cells", is_active=True)

        for index in range(12):
            self._create_question_with_two_choices(topic, f"Question #{index + 1}")

        response = self.client.post(
            "/api/attempt/",
            {"topic": topic.id, "subject": subject.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        attempt = Attempt.objects.get(id=response.data["id"])
        self.assertEqual(attempt.student_id, student.id)
        self.assertEqual(attempt.attempt_questions.count(), 10)
        self.assertEqual(
            list(attempt.attempt_questions.order_by("order").values_list("order", flat=True)),
            list(range(1, 11)),
        )

    def test_finish_attempt_calculates_correct_and_wrong_answers(self):
        self._authenticate_student("student_attempt_2")
        subject = Subject.objects.create(name="Physics")
        topic = Topic.objects.create(subject=subject, title="Mechanics", is_active=True)

        for index in range(10):
            self._create_question_with_two_choices(topic, f"Q{index + 1}")

        start_response = self.client.post(
            "/api/attempt/",
            {"topic": topic.id, "subject": subject.id},
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

        self._authenticate_student("student_attempt_owner")
        start_response = self.client.post(
            "/api/attempt/",
            {"topic": topic.id, "subject": subject.id},
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
