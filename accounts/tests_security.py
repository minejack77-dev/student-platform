from unittest.mock import patch
import base64
import socket

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient, APITestCase

from accounts.models import Student, Teacher, User, teacher_learning_permissions
from learning.models import Group, Subject, Topic
from learning.permissions import has_student_profile, has_teacher_profile


class AccountSecurityTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(username="security_admin", password="Synthetic-Test-Password42!")
        cls.student_user = User.objects.create_user(username="security_student", password="Synthetic-Test-Password42!")
        cls.other_user = User.objects.create_user(username="other_student")
        cls.student = Student.objects.create(user=cls.student_user)
        cls.other_student = Student.objects.create(user=cls.other_user)
        cls.teacher_user = User.objects.create_user(username="security_teacher", role=User.Role.TEACHER)
        cls.teacher = Teacher.objects.create(user=cls.teacher_user)
        cls.teacher_user.user_permissions.add(*teacher_learning_permissions())
        cls.other_teacher_user = User.objects.create_user(username="other_teacher", role=User.Role.TEACHER)
        cls.other_teacher = Teacher.objects.create(user=cls.other_teacher_user)
        cls.staff = User.objects.create_user(username="security_staff", is_staff=True)
        cls.group = Group.objects.create(name="Private group", teacher=cls.other_teacher)
        cls.group.students.add(cls.other_student)
        cls.topic = Topic.objects.create(subject=Subject.objects.create(name="Security subject"), title="Topic")

    def test_administrative_routes_deny_all_methods_for_non_admins(self):
        resources = (
            ("user", self.admin.pk, {"username": "injected_teacher", "password": "Synthetic-Test-Password42!", "role": "teacher"}),
            ("teacher", self.other_teacher.pk, {"user": self.student_user.pk}),
            ("student", self.other_student.pk, {"user": self.teacher_user.pk}),
        )
        for actor in (None, self.student_user, self.teacher_user, self.staff):
            self.client.force_authenticate(actor)
            for resource, pk, payload in resources:
                routes = (
                    ("get", f"/api/{resource}/", None),
                    ("post", f"/api/{resource}/", payload),
                    ("get", f"/api/{resource}/{pk}/", None),
                    ("head", f"/api/{resource}/{pk}/", None),
                    ("options", f"/api/{resource}/", None),
                    ("put", f"/api/{resource}/{pk}/", payload),
                    ("patch", f"/api/{resource}/{pk}/", payload),
                    ("delete", f"/api/{resource}/{pk}/", None),
                )
                for method, url, data in routes:
                    with self.subTest(actor=getattr(actor, "username", "anonymous"), method=method, url=url):
                        response = getattr(self.client, method)(url, data, format="json")
                        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="injected_teacher").exists())
        self.assertFalse(Teacher.objects.filter(user=self.student_user).exists())
        self.assertFalse(Student.objects.filter(user=self.teacher_user).exists())
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())
        self.assertTrue(Teacher.objects.filter(pk=self.other_teacher.pk).exists())
        self.assertTrue(Student.objects.filter(pk=self.other_student.pk).exists())

    def test_password_email_activation_and_self_promotion_cannot_be_modified(self):
        self.client.force_authenticate(self.student_user)
        for user in (self.admin, self.other_user, self.student_user):
            before = User.objects.filter(pk=user.pk).values().get()
            for payload in (
                {"password": "Attacker-Test-Password42!"},
                {"email": "attacker@example.invalid"},
                {"is_active": False},
                {"role": "teacher", "is_staff": True, "is_superuser": True},
            ):
                with self.subTest(user=user.pk, fields=list(payload)):
                    response = self.client.patch(f"/api/user/{user.pk}/", payload, format="json")
                    self.assertEqual(response.status_code, 403)
                    self.assertEqual(User.objects.filter(pk=user.pk).values().get(), before)

    def test_self_enrollment_and_foreign_profile_edits_leave_relations_unchanged(self):
        self.client.force_authenticate(self.student_user)
        for profile in (self.student, self.other_student):
            for payload in ({"groups": [self.group.pk]}, {"groups": []}, {"user": self.teacher_user.pk}):
                self.assertEqual(self.client.patch(f"/api/student/{profile.pk}/", payload, format="json").status_code, 403)
        self.client.force_authenticate(self.teacher_user)
        for profile in (self.teacher, self.other_teacher):
            for payload in ({"groups": [self.group.pk]}, {"topics": [self.topic.pk]}, {"user": self.student_user.pk}):
                self.assertEqual(self.client.patch(f"/api/teacher/{profile.pk}/", payload, format="json").status_code, 403)
        self.group.refresh_from_db()
        self.assertEqual(self.group.teacher_id, self.other_teacher.pk)
        self.assertEqual(list(self.group.students.all()), [self.other_student])
        self.assertFalse(self.teacher.topics.exists())
        self.assertFalse(self.other_teacher.topics.exists())

    def test_staff_and_model_permissions_do_not_imply_account_administrator(self):
        self.staff.user_permissions.add(*Permission.objects.filter(content_type__app_label="accounts"))
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get("/api/user/").status_code, 403)
        self.assertEqual(self.client.patch(f"/api/user/{self.admin.pk}/", {"password": "Synthetic-Test-Password43!"}, format="json").status_code, 403)
        self.assertFalse(has_teacher_profile(self.staff))
        self.assertFalse(has_student_profile(self.staff))

    def test_inactive_superuser_is_denied(self):
        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/user/").status_code, 403)

    def test_superuser_can_manage_accounts(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post("/api/user/", {"username": "managed_student", "password": "Synthetic-Test-Password42!", "role": "student"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        user_id = response.data["id"]
        url = f"/api/user/{user_id}/"
        self.assertEqual(self.client.get("/api/user/").status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.put(url, {"username": "managed_renamed", "email": "managed@example.invalid"}, format="json").status_code, 200)
        response = self.client.patch(url, {"password": "Synthetic-Test-Password43!", "is_active": False}, format="json")
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(pk=user_id)
        self.assertTrue(user.check_password("Synthetic-Test-Password43!"))
        self.assertFalse(user.is_active)
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(User.objects.filter(pk=user_id).exists())

    def test_superuser_can_manage_profiles_but_creation_does_not_grant_permissions(self):
        self.client.force_authenticate(self.admin)
        for resource, role, model in (("teacher", User.Role.TEACHER, Teacher), ("student", User.Role.STUDENT, Student)):
            user = User.objects.create_user(username=f"managed_{resource}_profile", role=role)
            response = self.client.post(f"/api/{resource}/", {"user": user.pk}, format="json")
            self.assertEqual(response.status_code, 201, response.data)
            url = f"/api/{resource}/{response.data['id']}/"
            self.assertEqual(self.client.get(f"/api/{resource}/").status_code, 200)
            self.assertEqual(self.client.get(url).status_code, 200)
            self.assertEqual(self.client.put(url, {"user": user.pk}, format="json").status_code, 200)
            self.assertEqual(self.client.patch(url, {}, format="json").status_code, 200)
            self.assertFalse(user.user_permissions.exists())
            self.assertEqual(self.client.delete(url).status_code, 204)
            self.assertFalse(model.objects.filter(user=user).exists())

    def test_profile_owner_is_immutable_even_for_superuser(self):
        self.client.force_authenticate(self.admin)
        for resource, profile, role in (("teacher", self.teacher, User.Role.TEACHER), ("student", self.student, User.Role.STUDENT)):
            replacement = User.objects.create_user(username=f"replacement_{resource}", role=role)
            for method in ("put", "patch"):
                response = getattr(self.client, method)(f"/api/{resource}/{profile.pk}/", {"user": replacement.pk}, format="json")
                self.assertEqual(response.status_code, 400, response.data)
            profile.refresh_from_db()
            self.assertNotEqual(profile.user_id, replacement.pk)
            profile.user = replacement
            with self.assertRaises(ValidationError):
                profile.save()

    def test_managed_relations_are_rejected_individually_on_create_and_update(self):
        self.client.force_authenticate(self.admin)
        for resource, profile, role, fields in (
            ("teacher", self.teacher, User.Role.TEACHER, {"groups": [self.group.pk], "topics": [self.topic.pk]}),
            ("student", self.student, User.Role.STUDENT, {"groups": [self.group.pk]}),
        ):
            new_user = User.objects.create_user(username=f"relations_{resource}", role=role)
            for field, value in fields.items():
                for method in ("put", "patch"):
                    response = getattr(self.client, method)(f"/api/{resource}/{profile.pk}/", {"user": profile.user_id, field: value}, format="json")
                    self.assertEqual(response.status_code, 400, response.data)
                response = self.client.post(f"/api/{resource}/", {"user": new_user.pk, field: value}, format="json")
                self.assertEqual(response.status_code, 400, response.data)
            self.assertFalse(type(profile).objects.filter(user=new_user).exists())

    def test_student_role_cannot_receive_teacher_profile(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post("/api/teacher/", {"user": self.student_user.pk}, format="json")
        self.assertEqual(response.status_code, 400)
        with self.assertRaises(ValidationError):
            Teacher.objects.create(user=self.student_user)
        self.assertFalse(Teacher.objects.filter(user=self.student_user).exists())

    def test_profile_save_does_not_grant_or_restore_permissions(self):
        self.other_teacher.save()
        self.other_teacher.save()
        self.assertFalse(self.other_teacher_user.user_permissions.exists())
        self.teacher_user.user_permissions.clear()
        self.teacher.save()
        self.assertFalse(self.teacher_user.user_permissions.exists())
        self.client.force_authenticate(self.teacher_user)
        self.assertEqual(self.client.get("/api/question/").status_code, 403)

    def test_explicit_permissions_work_and_are_revoked_when_profile_is_deleted(self):
        self.client.force_authenticate(self.teacher_user)
        self.assertEqual(self.client.get("/api/question/").status_code, 200)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(f"/api/teacher/{self.teacher.pk}/").status_code, 204)
        self.assertFalse(self.teacher_user.user_permissions.filter(content_type__app_label="learning").exists())
        self.client.force_authenticate(self.teacher_user)
        self.assertEqual(self.client.get("/api/question/").status_code, 403)
        Teacher.objects.create(user=self.teacher_user)
        self.client.force_authenticate(User.objects.get(pk=self.teacher_user.pk))
        self.assertEqual(self.client.get("/api/question/").status_code, 403)

    def test_role_revocation_disables_stale_profile_and_permissions(self):
        self.teacher_user.role = User.Role.STUDENT
        self.teacher_user.save(update_fields=["role"])
        self.assertFalse(has_teacher_profile(self.teacher_user))
        self.assertFalse(self.teacher_user.user_permissions.filter(content_type__app_label="learning").exists())
        self.client.force_authenticate(self.teacher_user)
        self.assertEqual(self.client.get("/api/question/").status_code, 403)
        self.teacher_user.role = User.Role.TEACHER
        self.teacher_user.save(update_fields=["role"])
        self.teacher.save()
        self.assertFalse(self.teacher_user.user_permissions.exists())

    def test_login_me_assignments_and_logout_keep_working_with_real_session(self):
        client = APIClient(enforce_csrf_checks=True)
        client.get("/api/auth/csrf/")
        response = client.post("/api/auth/login/", {"username": self.student_user.username, "password": "Synthetic-Test-Password42!"}, format="json", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.student_user.pk)
        self.assertEqual(client.get("/api/auth/me/").data["id"], self.student_user.pk)
        self.assertEqual(client.get("/api/student/me-assignments/").status_code, 200)
        self.assertEqual(client.get("/api/student/me-assignments/?all=true").status_code, 200)
        self.assertEqual(client.get("/api/user/").status_code, 403)
        response = client.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(client.get("/api/auth/me/").status_code, 403)

    def test_student_push_action_remains_self_scoped(self):
        self.client.force_authenticate(self.student_user)
        with patch("learning.tasks.send_user_push_task.delay") as send:
            response = self.client.post("/api/student/test-push/", {"user": self.other_user.pk}, format="json")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(send.call_args.args[0], self.student_user.pk)

    def test_login_requires_csrf_and_rejects_foreign_origin(self):
        client = APIClient(enforce_csrf_checks=True)
        payload = {"username": self.student_user.username, "password": "Synthetic-Test-Password42!"}
        self.assertEqual(client.post("/api/auth/login/", payload, format="json").status_code, 403)
        client.get("/api/auth/csrf/")
        token = client.cookies["csrftoken"].value
        for format_name in ("json", "multipart"):
            self.assertEqual(client.post("/api/auth/login/", payload, format=format_name, HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://attacker.invalid").status_code, 403)
        self.assertEqual(client.post("/api/auth/login/", payload, format="json", HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertIn("no-store", client.get("/api/auth/me/")["Cache-Control"])

    def test_password_validators_apply_to_create_reset_and_invalidate_old_session(self):
        self.client.force_authenticate(self.admin)
        for password in ("12345678", "password"):
            self.assertEqual(self.client.patch(f"/api/user/{self.student_user.pk}/", {"password": password}, format="json").status_code, 400)
            self.assertEqual(self.client.post("/api/user/", {"username": "weak_user", "password": password}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(f"/api/user/{self.student_user.pk}/", {"password": self.student_user.username}, format="json").status_code, 400)
        victim = APIClient()
        victim.force_login(self.student_user)
        password = "  Synthetic-Untrimmed-Passphrase42!  "
        response = self.client.patch(f"/api/user/{self.student_user.pk}/", {"password": password}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.student_user.refresh_from_db()
        self.assertTrue(self.student_user.check_password(password))
        self.assertFalse(self.student_user.check_password(password.strip()))
        self.assertEqual(victim.get("/api/auth/me/").status_code, 403)


class PushSecurityTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        cls.user = User.objects.create_user(username="push_a")
        cls.other = User.objects.create_user(username="push_b")
        key = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        cls.keys = {"auth": base64.urlsafe_b64encode(b"0123456789abcdef").decode().rstrip("="), "p256dh": base64.urlsafe_b64encode(key).decode().rstrip("=")}

    def setUp(self):
        self.client.force_authenticate(self.user)

    def test_unsafe_endpoints_and_invalid_keys_are_rejected_before_network(self):
        from webpush.models import PushInformation
        with patch("accounts.push.socket.getaddrinfo") as dns:
            for endpoint in ("http://127.0.0.1/push", "https://[::1]/push", "https://169.254.169.254/push", "https://fcm.googleapis.com.attacker.invalid/push", "https://fcm.googleapis.com:444/push", "https://user@fcm.googleapis.com/push", "https://example.invalid/push"):
                response = self.client.post("/api/push/subscribe/", {"endpoint": endpoint, "keys": self.keys}, format="json")
                self.assertEqual(response.status_code, 400)
            self.assertEqual(self.client.post("/api/push/subscribe/", {}, format="json").status_code, 400)
            self.assertEqual(self.client.post("/api/push/subscribe/", {"endpoint": "https://fcm.googleapis.com/push", "keys": {"auth": "bad", "p256dh": "bad"}}, format="json").status_code, 400)
            dns.assert_not_called()
        self.assertFalse(PushInformation.objects.exists())

    def test_endpoint_cannot_overwrite_another_user_and_unsubscribe_is_scoped(self):
        from webpush.models import PushInformation
        payload = {"endpoint": "https://fcm.googleapis.com/push/synthetic", "keys": self.keys}
        self.assertEqual(self.client.post("/api/push/subscribe/", payload, format="json").status_code, 200)
        self.assertEqual(self.client.post("/api/push/subscribe/", payload, format="json").status_code, 200)
        self.assertEqual(PushInformation.objects.count(), 1)
        other = APIClient()
        other.force_authenticate(self.other)
        self.assertEqual(other.post("/api/push/subscribe/", payload, format="json").status_code, 409)
        self.assertEqual(other.post("/api/push/unsubscribe/", format="json").status_code, 204)
        self.assertEqual(PushInformation.objects.count(), 1)
        self.assertEqual(self.client.post("/api/auth/logout/", format="json").status_code, 204)
        self.assertFalse(PushInformation.objects.exists())
        self.assertEqual(other.post("/api/push/subscribe/", payload, format="json").status_code, 200)

    def test_subscription_count_is_bounded(self):
        for index in range(6):
            response = self.client.post("/api/push/subscribe/", {"endpoint": f"https://fcm.googleapis.com/push/{index}", "keys": self.keys}, format="json")
            self.assertEqual(response.status_code, 200 if index < 5 else 400)

    def test_sender_rejects_private_dns_and_pins_public_dns_without_redirects(self):
        from accounts.push import SafePushSession
        from rest_framework.exceptions import ValidationError
        from unittest.mock import MagicMock
        private = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with SafePushSession() as session, patch("accounts.push.socket.getaddrinfo", return_value=private), patch("requests.Session.request") as transport:
            with self.assertRaises(ValidationError):
                session.post("https://fcm.googleapis.com/push/synthetic")
            transport.assert_not_called()
        public = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
        response = MagicMock()
        response.iter_content.return_value = iter([b"safe"])
        with SafePushSession() as session, patch("accounts.push.socket.getaddrinfo", return_value=public) as dns, patch("requests.Session.request", return_value=response) as transport:
            session.post("https://fcm.googleapis.com/push/synthetic", allow_redirects=True, timeout=None)
            dns.assert_called_once()
            self.assertEqual(transport.call_args.args[1], "https://8.8.8.8/push/synthetic")
            self.assertFalse(transport.call_args.kwargs["allow_redirects"])
            self.assertEqual(transport.call_args.kwargs["timeout"], (3, 5))
            self.assertEqual(transport.call_args.kwargs["headers"]["Host"], "fcm.googleapis.com")
            self.assertTrue(transport.call_args.kwargs["verify"])
            self.assertEqual(session.get_adapter("https://").poolmanager.connection_pool_kw["server_hostname"], "fcm.googleapis.com")

    def test_test_notification_is_queued_without_synchronous_network(self):
        with patch("learning.tasks.send_user_push_task.delay") as enqueue, patch("requests.Session.request") as network:
            self.assertEqual(self.client.post("/api/push/test/").status_code, 202)
            enqueue.assert_called_once()
            network.assert_not_called()
