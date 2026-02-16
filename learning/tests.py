from datetime import timedelta

from django.db import IntegrityError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Student, Teacher, User
from learning.models import Group, GroupTeachingAssignment, Question, Subject, Topic


class LearningApiTests(APITestCase):
    def setUp(self):
        self.auth_user = User.objects.create_user(
            username="teacher_api",
            password="StrongPass123",
            role=User.Role.TEACHER,
        )
        Teacher.objects.create(user=self.auth_user)
        self.client.force_authenticate(self.auth_user)

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
