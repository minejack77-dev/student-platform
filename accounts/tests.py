from datetime import date

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Student, Teacher, User
from learning.models import (
    Group,
    GroupTopicSchedule,
    GroupTeachingAssignment,
    Question,
    Subject,
    Task,
    Topic,
)


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

    def test_user_can_have_both_teacher_and_student_profiles(self):
        user = User.objects.create_user(
            username="dual_role_user",
            password="StrongPass123",
            role=User.Role.TEACHER,
        )
        teacher = Teacher.objects.create(user=user)

        student_response = self.client.post(
            "/api/student/",
            {"user": user.id},
            format="json",
        )
        self.assertEqual(student_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Student.objects.filter(user=user).exists())

        self.client.force_authenticate(user)
        me_assignments_response = self.client.get("/api/student/me-assignments/")
        self.assertEqual(me_assignments_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_assignments_response.data["student"], student_response.data["id"])
        self.assertEqual(len(me_assignments_response.data["results"]), 7)
        self.assertTrue(all(item["items"] == [] for item in me_assignments_response.data["results"]))
        self.assertEqual(teacher.user_id, user.id)

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

    def test_student_me_assignments_returns_date_based_schedule(self):
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
        assignment = GroupTeachingAssignment.objects.create(
            group=group,
            teacher=teacher,
            subject=subject,
            topic=topic,
        )
        schedule_entry = GroupTopicSchedule.objects.create(
            group=group,
            teacher=teacher,
            topic=topic,
            scheduled_for="2026-05-11",
        )
        for index in range(3):
            Question.objects.create(topic=topic, text=f"Question #{index + 1}")

        self.client.force_authenticate(student_user)
        response = self.client.get(
            "/api/student/me-assignments/",
            {"start_date": "2026-05-11", "days": 3},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["student"], student.id)
        self.assertEqual(response.data["start_date"], date(2026, 5, 11))
        self.assertEqual(response.data["days"], 3)
        self.assertEqual(len(response.data["results"]), 3)
        self.assertEqual(response.data["results"][0]["date"], date(2026, 5, 11))
        self.assertEqual(len(response.data["results"][0]["items"]), 1)
        scheduled_item = response.data["results"][0]["items"][0]
        self.assertEqual(scheduled_item["group_id"], group.id)
        self.assertEqual(scheduled_item["teacher_id"], teacher.id)
        self.assertEqual(scheduled_item["teacher_username"], "teacher_for_assignments")
        self.assertEqual(scheduled_item["subject_id"], assignment.subject_id)
        self.assertEqual(scheduled_item["subject_name"], "Physics")
        self.assertEqual(scheduled_item["topic_id"], topic.id)
        self.assertEqual(scheduled_item["topic_title"], "Dynamics")
        self.assertEqual(scheduled_item["schedule_entry_id"], schedule_entry.id)
        self.assertEqual(scheduled_item["active_question_count"], 3)
        self.assertEqual(scheduled_item["required_question_count"], 10)
        self.assertIsNone(scheduled_item["attempt_id"])
        self.assertIsNone(scheduled_item["attempt_status"])
        self.assertIsNone(scheduled_item["correct_count"])
        self.assertIsNone(scheduled_item["result_outcome"])
        self.assertEqual(response.data["results"][1]["items"], [])

    def test_student_me_assignments_returns_task_specific_required_question_count(self):
        student_user = User.objects.create_user(
            username="student_assignments_custom_count",
            password="StrongPass123",
            role=User.Role.STUDENT,
        )
        student = Student.objects.create(user=student_user)
        teacher_user = User.objects.create_user(
            username="teacher_for_custom_assignments",
            password="StrongPass123",
            role=User.Role.TEACHER,
        )
        teacher = Teacher.objects.create(user=teacher_user)

        subject = Subject.objects.create(name="English")
        topic = Topic.objects.create(subject=subject, title="Lesson A")
        task = Task.objects.create(
            topic=topic,
            title="Task 4",
            questions_per_attempt=4,
            passing_correct_answers=3,
        )

        group = Group.objects.create(name="Custom Homework Group", is_active=True)
        group.students.add(student)
        GroupTeachingAssignment.objects.create(
            group=group,
            teacher=teacher,
            subject=subject,
            topic=topic,
            task=task,
        )
        GroupTopicSchedule.objects.create(
            group=group,
            teacher=teacher,
            topic=topic,
            task=task,
            scheduled_for="2026-05-21",
        )
        for index in range(6):
            Question.objects.create(
                topic=topic,
                task=task,
                text=f"Question #{index + 1}",
            )

        self.client.force_authenticate(student_user)
        response = self.client.get(
            "/api/student/me-assignments/",
            {"start_date": "2026-05-21", "days": 1},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        scheduled_item = response.data["results"][0]["items"][0]
        self.assertEqual(scheduled_item["active_question_count"], 6)
        self.assertEqual(scheduled_item["required_question_count"], 4)

    def test_student_me_assignments_rejects_non_student_user(self):
        response = self.client.get("/api/student/me-assignments/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # def test_auth_csrf_endpoint_sets_cookie(self):
    #     self.client.force_authenticate(user=None)
    #     response = self.client.get("/api/auth/csrf/")

    #     self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    #     self.assertIn("csrftoken", response.cookies)

    # def test_login_returns_authenticated_user_payload(self):
    #     self.client.force_authenticate(user=None)
    #     user = User.objects.create_user(
    #         username="login_user",
    #         password="StrongPass123",
    #         role=User.Role.STUDENT,
    #         email="login@example.com",
    #     )
    #     student = Student.objects.create(user=user)

    #     response = self.client.post(
    #         "/api/auth/login/",
    #         {"username": "login_user", "password": "StrongPass123"},
    #         format="json",
    #     )

    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     self.assertEqual(response.data["id"], user.id)
    #     self.assertEqual(response.data["role"], User.Role.STUDENT)
    #     self.assertEqual(response.data["student_id"], student.id)
    #     self.assertIsNone(response.data["teacher_id"])
    #     self.assertTrue(response.data["is_authenticated"])

    # def test_login_rejects_invalid_credentials(self):
    #     self.client.force_authenticate(user=None)
    #     User.objects.create_user(
    #         username="bad_login_user",
    #         password="StrongPass123",
    #         role=User.Role.TEACHER,
    #     )

    #     response = self.client.post(
    #         "/api/auth/login/",
    #         {"username": "bad_login_user", "password": "WrongPassword123"},
    #         format="json",
    #     )

    #     self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # def test_me_returns_current_user(self):
    #     user = User.objects.create_user(
    #         username="me_user",
    #         password="StrongPass123",
    #         role=User.Role.TEACHER,
    #         email="me@example.com",
    #     )
    #     teacher = Teacher.objects.create(user=user)

    #     self.client.force_authenticate(user)
    #     response = self.client.get("/api/auth/me/")

    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     self.assertEqual(response.data["id"], user.id)
    #     self.assertEqual(response.data["teacher_id"], teacher.id)
    #     self.assertIsNone(response.data["student_id"])

    # def test_logout_ends_authenticated_session(self):
    #     self.client.force_authenticate(user=None)
    #     user = User.objects.create_user(
    #         username="logout_user",
    #         password="StrongPass123",
    #         role=User.Role.STUDENT,
    #     )
    #     Student.objects.create(user=user)

    #     login_response = self.client.post(
    #         "/api/auth/login/",
    #         {"username": "logout_user", "password": "StrongPass123"},
    #         format="json",
    #     )
    #     self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    #     logout_response = self.client.post("/api/auth/logout/")
    #     self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)

    #     me_response = self.client.get("/api/auth/me/")
    #     self.assertEqual(me_response.status_code, status.HTTP_403_FORBIDDEN)
