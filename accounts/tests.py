from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Student, Teacher, User
from learning.models import Group, GroupTeachingAssignment, Subject, Topic


class AccountsApiTests(APITestCase):
    def setUp(self):
        self.auth_user = User.objects.create_user(
            username="api_admin",
            password="StrongPass123",
            role=User.Role.TEACHER,
            email="api_admin@example.com",
        )
        self.client.force_authenticate(self.auth_user)

    def test_create_student_user_creates_student_profile_and_hashes_password(self):
        response = self.client.post(
            "/api/user/",
            {
                "username": "student_1",
                "password": "StrongPass123",
                "email": "student_1@example.com",
                "role": User.Role.STUDENT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", response.data)

        user = User.objects.get(username="student_1")
        self.assertTrue(user.check_password("StrongPass123"))
        student = Student.objects.get(user=user)

        self.assertEqual(response.data["student_id"], student.id)
        self.assertIsNone(response.data["teacher_id"])

    def test_create_teacher_user_creates_teacher_profile(self):
        response = self.client.post(
            "/api/user/",
            {
                "username": "teacher_1",
                "password": "StrongPass123",
                "email": "teacher_1@example.com",
                "role": User.Role.TEACHER,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="teacher_1")
        teacher = Teacher.objects.get(user=user)

        self.assertEqual(response.data["teacher_id"], teacher.id)
        self.assertIsNone(response.data["student_id"])

    def test_user_role_cannot_be_changed_after_creation(self):
        user = User.objects.create_user(
            username="student_for_update",
            password="StrongPass123",
            role=User.Role.STUDENT,
        )
        Student.objects.create(user=user)

        response = self.client.patch(
            f"/api/user/{user.id}/",
            {"role": User.Role.TEACHER},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_student_can_be_assigned_to_multiple_groups(self):
        student_user = User.objects.create_user(
            username="student_groups",
            password="StrongPass123",
            role=User.Role.STUDENT,
        )
        student = Student.objects.create(user=student_user)
        group_a = Group.objects.create(name="Group A")
        group_b = Group.objects.create(name="Group B")

        response = self.client.patch(
            f"/api/student/{student.id}/",
            {"groups": [group_a.id, group_b.id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student.refresh_from_db()
        self.assertSetEqual(
            set(student.groups.values_list("id", flat=True)),
            {group_a.id, group_b.id},
        )

    def test_teacher_can_be_assigned_groups_and_topics(self):
        teacher_user = User.objects.create_user(
            username="teacher_groups_topics",
            password="StrongPass123",
            role=User.Role.TEACHER,
        )
        teacher = Teacher.objects.create(user=teacher_user)

        subject = Subject.objects.create(name="Math")
        topic_a = Topic.objects.create(subject=subject, title="Topic A")
        topic_b = Topic.objects.create(subject=subject, title="Topic B")
        group_a = Group.objects.create(name="Teacher Group A")
        group_b = Group.objects.create(name="Teacher Group B")

        response = self.client.patch(
            f"/api/teacher/{teacher.id}/",
            {
                "topics": [topic_a.id, topic_b.id],
                "groups": [group_a.id, group_b.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        teacher.refresh_from_db()
        group_a.refresh_from_db()
        group_b.refresh_from_db()

        self.assertSetEqual(
            set(teacher.topics.values_list("id", flat=True)),
            {topic_a.id, topic_b.id},
        )
        self.assertEqual(group_a.teacher_id, teacher.id)
        self.assertEqual(group_b.teacher_id, teacher.id)

    def test_student_me_assignments_returns_subject_and_topic(self):
        student_user = User.objects.create_user(
            username="student_assignments",
            password="StrongPass123",
            role=User.Role.STUDENT,
        )
        student = Student.objects.create(user=student_user)
        teacher_user = User.objects.create_user(
            username="teacher_for_assignments",
            password="StrongPass123",
            role=User.Role.TEACHER,
        )
        teacher = Teacher.objects.create(user=teacher_user)

        subject = Subject.objects.create(name="Physics")
        topic = Topic.objects.create(subject=subject, title="Dynamics")

        group = Group.objects.create(name="Homework Group", is_active=True)
        group.students.add(student)
        GroupTeachingAssignment.objects.create(
            group=group,
            teacher=teacher,
            subject=subject,
            topic=topic,
        )

        self.client.force_authenticate(student_user)
        response = self.client.get("/api/student/me-assignments/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["group_id"], group.id)
        self.assertEqual(response.data[0]["teacher_id"], teacher.id)
        self.assertEqual(response.data[0]["teacher_username"], "teacher_for_assignments")
        self.assertEqual(response.data[0]["subject_id"], subject.id)
        self.assertEqual(response.data[0]["subject_name"], "Physics")
        self.assertEqual(response.data[0]["topic_id"], topic.id)
        self.assertEqual(response.data[0]["topic_title"], "Dynamics")

    def test_student_me_assignments_rejects_non_student_user(self):
        response = self.client.get("/api/student/me-assignments/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
