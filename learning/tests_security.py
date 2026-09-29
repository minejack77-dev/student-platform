from django.utils import timezone
from django.contrib.auth.models import Permission
from unittest.mock import patch
from rest_framework.test import APITestCase

from accounts.models import User, Teacher, Student, teacher_learning_permissions
from learning.models import (
    Group, GroupTeachingAssignment, GroupTopicSchedule, Subject, Topic, Task,
    Question, Attempt, AttemptQuestion,
    Workbook, Unit,
    Choice, Answer, MatchingPair,
)


class GroupSecurityTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(username="group_admin")
        cls.owner_user = User.objects.create_user(username="owner", role="teacher")
        cls.assigned_user = User.objects.create_user(username="assigned", role="teacher")
        cls.outsider_user = User.objects.create_user(username="outsider", role="teacher", is_staff=True)
        cls.owner = Teacher.objects.create(user=cls.owner_user)
        cls.assigned = Teacher.objects.create(user=cls.assigned_user)
        cls.outsider = Teacher.objects.create(user=cls.outsider_user)
        for user in (cls.owner_user, cls.assigned_user, cls.outsider_user):
            user.user_permissions.add(*teacher_learning_permissions())
        cls.student_user = User.objects.create_user(username="member")
        cls.student = Student.objects.create(user=cls.student_user)
        cls.other_student_user = User.objects.create_user(username="nonmember")
        cls.other_student = Student.objects.create(user=cls.other_student_user)
        cls.group = Group.objects.create(name="Owned", teacher=cls.owner)
        cls.group.students.add(cls.student)
        cls.other_group = Group.objects.create(name="Other", teacher=cls.outsider)
        cls.orphan = Group.objects.create(name="Unowned")
        cls.subject = Subject.objects.create(name="Subject")
        cls.topic = Topic.objects.create(subject=cls.subject, title="Topic")
        cls.task = Task.objects.create(topic=cls.topic, title="Task", questions_per_attempt=1, passing_correct_answers=1)
        cls.question = Question.objects.create(topic=cls.topic, task=cls.task, text="Question")
        cls.assignment = GroupTeachingAssignment.objects.create(group=cls.group, teacher=cls.assigned, subject=cls.subject)
        cls.entry = GroupTopicSchedule.objects.create(group=cls.group, teacher=cls.assigned, topic=cls.topic, task=cls.task, scheduled_for=timezone.localdate())
        cls.attempt = Attempt.objects.create(student=cls.student, topic=cls.topic, task=cls.task, schedule_entry=cls.entry)
        cls.aq = AttemptQuestion.objects.create(attempt=cls.attempt, question=cls.question, order=1)

    def test_foreign_group_is_hidden_and_takeover_and_self_assignment_are_denied(self):
        self.client.force_authenticate(self.outsider_user)
        url = f"/api/group/{self.group.pk}/"
        for method, suffix, payload in (
            ("get", "", None), ("patch", "", {"teacher": self.outsider.pk}),
            ("put", "", {"name": "Stolen", "teacher": self.outsider.pk}), ("delete", "", None),
            ("patch", "teacher-assignment/", {"subject": self.subject.pk}),
            ("get", "teacher-assignment/", None), ("delete", "teacher-assignment/", None),
            ("get", "topic-calendar/", None), ("patch", "topic-calendar/", {"date": str(timezone.localdate()), "task": self.task.pk}),
            ("delete", "topic-calendar/", {"schedule_entry": self.entry.pk}),
            ("get", "detailed-statistics/", None), ("get", "ranking/", None),
            ("get", "search-students/", {"q": "member"}), ("get", "find-student/", {"user_id": self.student_user.pk}),
            ("post", "add-student/", {"user_id": self.other_student_user.pk}),
            ("post", "remove-student/", {"user_id": self.student_user.pk}),
        ):
            with self.subTest(method=method, suffix=suffix):
                response = getattr(self.client, method)(url + suffix, payload, format="json")
                self.assertEqual(response.status_code, 404, response.data)
        self.group.refresh_from_db()
        self.assertEqual(self.group.teacher_id, self.owner.pk)
        self.assertTrue(self.group.students.filter(pk=self.student.pk).exists())
        self.assertFalse(self.group.students.filter(pk=self.other_student.pk).exists())
        self.assertFalse(GroupTeachingAssignment.objects.filter(group=self.group, teacher=self.outsider).exists())
        self.assertTrue(GroupTopicSchedule.objects.filter(pk=self.entry.pk).exists())

    def test_list_filters_do_not_widen_scope_and_orphans_require_admin(self):
        for user in (self.owner_user, self.assigned_user):
            self.client.force_authenticate(user)
            response = self.client.get("/api/group/")
            self.assertEqual({row["id"] for row in response.data["results"]}, {self.group.pk})
            self.assertEqual(self.client.get("/api/group/", {"id": self.other_group.pk}).data["results"], [])
            self.assertEqual(self.client.patch(f"/api/group/{self.orphan.pk}/", {"teacher": self.owner.pk}, format="json").status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(f"/api/group/{self.orphan.pk}/", {"teacher": self.owner.pk}, format="json").status_code, 200)

    def test_assigned_teacher_reads_but_cannot_manage_owner_members_or_invite(self):
        self.client.force_authenticate(self.assigned_user)
        url = f"/api/group/{self.group.pk}/"
        for suffix in ("", "ranking/", "detailed-statistics/", "topic-calendar/", "teacher-assignment/"):
            self.assertEqual(self.client.get(url + suffix).status_code, 200)
        self.assertFalse(self.client.get(url).data["can_manage_students"])
        for method, suffix, data in (
            ("patch", "", {"teacher": self.assigned.pk}), ("patch", "", {"name": "Renamed"}),
            ("delete", "", None), ("post", "add-student/", {"user_id": self.other_student_user.pk}),
            ("patch", "teacher-assignment/", {"teacher": self.outsider.pk, "subject": self.subject.pk}),
            ("patch", "topic-calendar/", {"teacher": self.owner.pk, "date": str(timezone.localdate()), "task": self.task.pk}),
        ):
            self.assertEqual(getattr(self.client, method)(url + suffix, data, format="json").status_code, 403)

    def test_owner_can_invite_and_assigned_teacher_can_manage_own_calendar(self):
        self.client.force_authenticate(self.owner_user)
        url = f"/api/group/{self.group.pk}/"
        response = self.client.patch(url + "teacher-assignment/", {"teacher": self.outsider.pk, "subject": self.subject.pk}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.post(url + "add-student/", {"user_id": self.other_student_user.pk}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(url, {"teacher": self.outsider.pk}, format="json").status_code, 400)
        self.client.force_authenticate(self.outsider_user)
        response = self.client.patch(url + "topic-calendar/", {"date": str(timezone.localdate()), "task": self.task.pk}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["teacher"], self.outsider.pk)

    def test_attempt_scope_owner_assigned_outsider_and_revoked(self):
        for user, code in ((self.owner_user, 200), (self.assigned_user, 200), (self.outsider_user, 404), (self.admin, 200)):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(f"/api/attempt/{self.attempt.pk}/").status_code, code)
            self.assertEqual(self.client.get(f"/api/attempt_question/{self.aq.pk}/").status_code, code)
        self.assignment.delete()
        self.client.force_authenticate(self.assigned_user)
        self.assertEqual(self.client.get(f"/api/attempt/{self.attempt.pk}/").status_code, 404)
        self.assertEqual(self.client.get("/api/attempt_question/", {"attempt": self.attempt.pk}).data["results"], [])
        self.assertEqual(self.client.get(f"/api/group/{self.group.pk}/").status_code, 404)

    def test_student_can_read_only_own_ranking_and_cannot_widen_scope(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.get(f"/api/group/{self.group.pk}/ranking/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("ranking", response.data)
        self.assertEqual(self.client.get(f"/api/group/{self.other_group.pk}/ranking/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/group/{self.group.pk}/").status_code, 403)

    def test_administrator_without_teacher_profile_can_manage_assignment_and_read_stats(self):
        self.client.force_authenticate(self.admin)
        url = f"/api/group/{self.group.pk}/"
        self.assertEqual(self.client.patch(url + "teacher-assignment/", {"teacher": self.outsider.pk, "subject": self.subject.pk}, format="json").status_code, 201)
        self.assertEqual(self.client.get(url + "detailed-statistics/").status_code, 200)
        self.assertEqual(self.client.get(url + "ranking/").status_code, 200)


class MaterialSecurityTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner_user = User.objects.create_user(username="author", role="teacher", is_staff=True)
        cls.other_user = User.objects.create_user(username="other_author", role="teacher", is_staff=True)
        for user in (cls.owner_user, cls.other_user):
            Teacher.objects.create(user=user)
            user.user_permissions.add(*teacher_learning_permissions())
        cls.admin = User.objects.create_superuser(username="material_admin")
        cls.subject = Subject.objects.create(name="Owned subject", owner=cls.owner_user)
        cls.workbook = Workbook.objects.create(subject=cls.subject, title="Owned workbook")
        cls.unit = Unit.objects.create(workbook=cls.workbook, title="Owned unit")
        cls.topic = Topic.objects.create(subject=cls.subject, unit=cls.unit, title="Owned lesson")
        cls.task = Task.objects.create(topic=cls.topic, title="Owned task", src="synthetic.xlsx")
        cls.question = Question.objects.create(topic=cls.topic, task=cls.task, text="Owned question")
        cls.other_subject = Subject.objects.create(name="Other subject", owner=cls.other_user)
        cls.unowned = Subject.objects.create(name="Legacy unowned")

    def test_other_author_can_read_but_cannot_change_or_delete_any_level(self):
        self.client.force_authenticate(self.other_user)
        for obj in (self.subject, self.workbook, self.unit, self.topic, self.task, self.question, self.unowned):
            url = f"/api/{obj._meta.model_name}/{obj.pk}/"
            self.assertEqual(self.client.get(url).status_code, 200)
            before = type(obj).objects.filter(pk=obj.pk).values().get()
            for method in ("patch", "put", "delete"):
                self.assertEqual(getattr(self.client, method)(url, {"is_active": False}, format="json").status_code, 403)
            self.assertEqual(type(obj).objects.filter(pk=obj.pk).values().get(), before)

    def test_cross_owner_parents_and_ownership_spoof_are_rejected(self):
        self.client.force_authenticate(self.other_user)
        for resource, payload in (
            ("workbook", {"subject": self.subject.pk, "title": "Injected"}),
            ("unit", {"workbook": self.workbook.pk, "title": "Injected"}),
            ("topic", {"subject": self.subject.pk, "title": "Injected"}),
            ("topic", {"unit": self.unit.pk, "title": "Injected"}),
            ("task", {"topic": self.topic.pk, "title": "Injected"}),
            ("question", {"task": self.task.pk, "text": "Injected"}),
        ):
            response = self.client.post(f"/api/{resource}/", payload, format="json")
            self.assertEqual(response.status_code, 400, response.data)
        response = self.client.post("/api/subject/", {"name": "Spoofed", "owner": self.owner_user.pk}, format="json")
        self.assertEqual(response.status_code, 400)
        self.client.force_authenticate(self.owner_user)
        response = self.client.patch(f"/api/workbook/{self.workbook.pk}/", {"subject": self.other_subject.pk}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(f"/api/subject/{self.subject.pk}/", {"owner": self.other_user.pk}, format="json")
        self.assertEqual(response.status_code, 400)
        self.workbook.refresh_from_db()
        self.assertEqual(self.workbook.subject_id, self.subject.pk)

    def test_author_can_create_own_collection_and_edit_descendants(self):
        self.client.force_authenticate(self.owner_user)
        response = self.client.post("/api/subject/", {"name": "New owned"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["owner"], self.owner_user.pk)
        for obj in (self.subject, self.workbook, self.unit, self.topic, self.task, self.question):
            response = self.client.patch(f"/api/{obj._meta.model_name}/{obj.pk}/", {"is_active": True}, format="json")
            self.assertEqual(response.status_code, 200, response.data)

    def test_foreign_import_undo_and_images_stop_before_processing(self):
        self.client.force_authenticate(self.other_user)
        with patch("learning.views.import_batch") as importer, patch("learning.views.undo_batch") as undo:
            self.assertEqual(self.client.post(f"/api/task/{self.task.pk}/import-questions/", {}, format="multipart").status_code, 403)
            self.assertEqual(self.client.post(f"/api/task/{self.task.pk}/undo-import/", {"token": "forged"}, format="json").status_code, 403)
        importer.assert_not_called()
        undo.assert_not_called()
        self.assertEqual(self.client.post(f"/api/question/{self.question.pk}/images/", {}, format="multipart").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/question/{self.question.pk}/images/999/").status_code, 403)

    def test_admin_import_requires_model_permissions_and_material_ownership(self):
        staff = User.objects.create_user(username="bare_staff", is_staff=True, role="teacher")
        Teacher.objects.create(user=staff)
        self.topic.src = "synthetic.xlsx"
        self.topic.save(update_fields=["src"])
        for actor, expected in ((staff, 403), (self.other_user, 404), (self.owner_user, 302), (self.admin, 302)):
            self.client.force_login(actor)
            for obj in (self.topic, self.task):
                with patch("learning.admin.import_questions_from_xls", return_value=[]) as importer:
                    response = self.client.post(f"/admin/learning/{obj._meta.model_name}/{obj.pk}/import-from-src/")
                    self.assertEqual(response.status_code, expected)
                    self.assertEqual(importer.called, expected == 302)
        staff.user_permissions.add(Permission.objects.get(content_type__app_label="learning", codename="change_task"))
        self.client.force_login(staff)
        with patch("learning.admin.import_questions_from_xls") as importer:
            self.assertEqual(self.client.post(f"/admin/learning/task/{self.task.pk}/import-from-src/").status_code, 403)
            importer.assert_not_called()

    def test_admin_options_and_regular_changes_follow_same_scope(self):
        staff = User.objects.create_user(username="options_staff", is_staff=True)
        self.client.force_login(staff)
        for suffix in ("workbook-options/?subject=" + str(self.subject.pk), "unit-options/?workbook=" + str(self.workbook.pk)):
            self.assertEqual(self.client.get("/admin/learning/topic/" + suffix).status_code, 403)
        self.client.force_login(self.other_user)
        response = self.client.get(f"/admin/learning/topic/workbook-options/?subject={self.subject.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
        response = self.client.get(f"/admin/learning/topic/{self.topic.pk}/change/")
        self.assertNotEqual(response.status_code, 200)
        self.client.force_login(self.owner_user)
        response = self.client.get(f"/admin/learning/topic/workbook-options/?subject={self.subject.pk}")
        self.assertEqual(response.json()["results"], [{"id": self.workbook.pk, "text": self.workbook.title}])

    def test_only_administrator_can_edit_legacy_unowned_material(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(f"/api/subject/{self.unowned.pk}/", {"description": "Reviewed"}, format="json").status_code, 200)

    def test_rich_text_api_reconstructs_allowed_markup_and_rejects_oversize(self):
        self.client.force_authenticate(self.owner_user)
        response = self.client.patch(f"/api/question/{self.question.pk}/", {
            "text": '<b onclick="bad()">Bold</b><img src="/media/test.png" onerror="bad()"><iframe src="https://example.invalid"></iframe>',
            "choices": [{"text": '<u onmouseover="bad()">Yes</u>', "is_correct": True}, {"text": "No", "is_correct": False}],
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn("onerror", response.data["text"])
        self.assertNotIn("onclick", response.data["text"])
        self.assertNotIn("iframe", response.data["text"])
        self.assertIn("<b>Bold</b>", response.data["text"])
        self.assertEqual(response.data["choices"][0]["text"], "<u>Yes</u>")
        self.assertEqual(self.client.patch(f"/api/question/{self.question.pk}/", {"text": "x" * 100001}, format="json").status_code, 400)


class AttemptSecurityTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="attempt_student")
        cls.student = Student.objects.create(user=cls.user)
        cls.teacher_user = User.objects.create_user(username="attempt_teacher", role="teacher")
        cls.teacher = Teacher.objects.create(user=cls.teacher_user)
        cls.subject = Subject.objects.create(name="Attempt security", owner=cls.teacher_user)
        cls.topic = Topic.objects.create(subject=cls.subject, title="Topic")
        cls.task = Task.objects.create(topic=cls.topic, title="Task", questions_per_attempt=1, passing_correct_answers=1)
        cls.group = Group.objects.create(name="Attempt group", teacher=cls.teacher)
        cls.group.students.add(cls.student)
        cls.entry = GroupTopicSchedule.objects.create(group=cls.group, teacher=cls.teacher, topic=cls.topic, task=cls.task, scheduled_for=timezone.localdate())
        cls.question = Question.objects.create(topic=cls.topic, task=cls.task, text="Question", question_type="single_choice")
        cls.correct = Choice.objects.create(question=cls.question, text="Correct", is_correct=True)
        cls.wrong = Choice.objects.create(question=cls.question, text="Wrong", is_correct=False)
        cls.attempt = Attempt.objects.create(student=cls.student, topic=cls.topic, task=cls.task, schedule_entry=cls.entry)
        cls.aq = AttemptQuestion.objects.create(attempt=cls.attempt, question=cls.question, order=1)

    def setUp(self):
        self.client.force_authenticate(self.user)

    def test_attempt_links_and_closed_metadata_cannot_be_patched(self):
        url = f"/api/attempt/{self.attempt.pk}/"
        for state in ("in_progress", "completed"):
            Attempt.objects.filter(pk=self.attempt.pk).update(status=state)
            before = Attempt.objects.filter(pk=self.attempt.pk).values().get()
            for payload in ({"schedule_entry": None}, {"schedule_entry": self.entry.pk}, {"task": self.task.pk}, {"topic": self.topic.pk}, {"student": self.student.pk}, {"finished_at": None}, {"status": "abandoned"}, {"status": "completed", "schedule_entry": None}):
                self.assertEqual(self.client.patch(url, payload, format="json").status_code, 400)
                self.assertEqual(Attempt.objects.filter(pk=self.attempt.pk).values().get(), before)

    def test_submit_is_idempotent_and_all_answer_mutations_are_blocked_afterwards(self):
        payload = {"answers": [{"attempt_question": self.aq.pk, "selected_choices": [self.correct.pk]}]}
        url = f"/api/attempt/{self.attempt.pk}/submit/"
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["correct_count"], 1)
        finished_at = response.data["finished_at"]
        self.assertEqual(self.client.post(url, payload, format="json").data["finished_at"], finished_at)
        answer = Answer.objects.get(attempt_question=self.aq)
        for method in ("put", "patch", "delete"):
            response = getattr(self.client, method)(f"/api/answer/{answer.pk}/", {"attempt_question": self.aq.pk, "selected_choices": [self.wrong.pk]}, format="json")
            self.assertIn(response.status_code, (400, 405))
        self.assertEqual(self.client.post("/api/answer/", {"attempt_question": self.aq.pk, "selected_choices": [self.wrong.pk]}, format="json").status_code, 400)
        self.assertEqual(list(answer.selected_choices.values_list("pk", flat=True)), [self.correct.pk])

    def test_expired_or_revoked_access_blocks_save_and_both_completion_routes(self):
        from datetime import timedelta
        cases = [(self.group, "is_active", False), (self.subject, "is_active", False), (self.topic, "is_active", False), (self.task, "is_active", False), (self.entry, "scheduled_for", timezone.localdate() - timedelta(days=1))]
        answer = {"attempt_question": self.aq.pk, "selected_choices": [self.correct.pk]}
        for obj, field, value in cases:
            old = getattr(obj, field)
            type(obj).objects.filter(pk=obj.pk).update(**{field: value})
            self.assertEqual(self.client.post("/api/answer/", answer, format="json").status_code, 400)
            self.assertEqual(self.client.patch(f"/api/attempt/{self.attempt.pk}/", {"status": "completed"}, format="json").status_code, 400)
            self.assertEqual(self.client.post(f"/api/attempt/{self.attempt.pk}/submit/", {"answers": [answer]}, format="json").status_code, 400)
            type(obj).objects.filter(pk=obj.pk).update(**{field: old})
        self.group.students.remove(self.student)
        self.assertEqual(self.client.post("/api/answer/", answer, format="json").status_code, 400)
        self.assertFalse(Answer.objects.filter(attempt_question=self.aq).exists())

    def test_matching_tokens_are_independent_stable_and_server_graded(self):
        self.question.question_type = "matching"
        self.question.save(update_fields=["question_type"])
        pairs = [MatchingPair.objects.create(question=self.question, left_content=f"Left {i}", right_content=f"Right {i}", order=i) for i in range(1, 3)]
        from learning.services.snapshots import capture_question
        # This case starts with matching content, before any student interaction.
        self.aq.content_snapshot = capture_question(self.question)
        self.aq.save(update_fields=["content_snapshot"])
        url = f"/api/attempt_question/{self.aq.pk}/"
        payload = self.client.get(url).data
        left = {item["id"] for item in payload["matching_left_items"]}
        right = {item["id"] for item in payload["matching_right_items"]}
        self.assertTrue(left.isdisjoint(right))
        self.assertTrue(all(isinstance(token, str) and not token.isdigit() for token in left | right))
        self.assertEqual(self.client.get(url).data, payload)
        for selection in ({token: token for token in left}, {str(pair.pk): pair.pk for pair in pairs}, {"Lforeign": next(iter(right))}):
            self.assertEqual(self.client.post("/api/answer/", {"attempt_question": self.aq.pk, "selected_matching_pairs": selection}, format="json").status_code, 400)
        from learning.services.matching import encode_matching
        correct = encode_matching(self.aq, {str(pair.pk): pair.pk for pair in pairs})
        response = self.client.post(f"/api/attempt/{self.attempt.pk}/submit/", {"answers": [{"attempt_question": self.aq.pk, "selected_matching_pairs": correct}]}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["correct_count"], 1)
        result = self.client.get(url).data
        self.assertEqual(result["correct_matching_pairs"], correct)
        self.assertEqual(result["answer"]["selected_matching_pairs"], correct)
