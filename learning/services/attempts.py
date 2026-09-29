from learning.services.snapshots import question_snapshot
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from learning.models import Answer, Attempt, Question


def require_schedule_access(entry, student_id):
    if entry is None or entry.scheduled_for != timezone.localdate():
        raise ValidationError({"code": "attempt_closed", "detail": "This test can only be completed on its scheduled date."})
    if (
        not entry.group.is_active or not entry.topic.is_active
        or not entry.topic.subject.is_active or not entry.task_id or not entry.task.is_active
        or not entry.group.students.filter(pk=student_id).exists()
    ):
        raise ValidationError({"code": "assignment_revoked"})


def require_attempt_write_access(attempt):
    if attempt.status != Attempt.Status.IN_PROGRESS:
        raise ValidationError({"code": "attempt_closed"})
    require_schedule_access(attempt.schedule_entry, attempt.student_id)
    if attempt.task_id != attempt.schedule_entry.task_id or attempt.topic_id != attempt.schedule_entry.topic_id:
        raise ValidationError({"code": "invalid_attempt_assignment"})


@transaction.atomic
def submit_attempt(*, attempt_id, context, answers=None, confirm_unanswered=False, use_saved_answers=False):
    from learning.serializers import AnswerSerializer

    attempt = Attempt.objects.select_for_update(of=("self",)).select_related("student__user", "schedule_entry__group", "schedule_entry__topic__subject", "schedule_entry__task").get(pk=attempt_id)
    user = context["request"].user
    if not user.is_active or attempt.student.user_id != user.pk:
        raise ValidationError({"code": "not_your_attempt"})
    if attempt.status == Attempt.Status.COMPLETED:
        return attempt
    require_attempt_write_access(attempt)
    questions = list(attempt.attempt_questions.select_related("question"))
    if use_saved_answers:
        answers = []
        for question in questions:
            saved = Answer.objects.filter(attempt_question=question).first()
            payload = dict(AnswerSerializer(saved, context=context).data) if saved else {}
            payload["attempt_question"] = question.pk
            answers.append(payload)
    if not isinstance(answers, list) or len(answers) != len(questions):
        raise ValidationError({"code": "incomplete_submission"})
    if any(not isinstance(item, dict) or type(item.get("attempt_question")) is not int for item in answers):
        raise ValidationError({"code": "incomplete_submission"})
    by_id = {item["attempt_question"]: item for item in answers}
    if set(by_id) != {q.pk for q in questions}:
        raise ValidationError({"code": "incomplete_submission"})
    unanswered = False
    for question in questions:
        serializer = AnswerSerializer(
            instance=Answer.objects.filter(attempt_question=question).first(),
            data=by_id[question.pk], context=context,
        )
        serializer.is_valid(raise_exception=True)
        if question_snapshot(question)["question_type"] == Question.QuestionType.MATCHING:
            unanswered |= len(serializer.validated_data.get("selected_matching_pairs", {})) < len(question_snapshot(question)["matching_pairs"])
        else:
            unanswered |= not bool(serializer.validated_data.get("selected_choices"))
        serializer.save()
    if unanswered and not confirm_unanswered:
        raise ValidationError({"code": "confirm_unanswered"})
    attempt.status = Attempt.Status.COMPLETED
    attempt.finished_at = timezone.now()
    attempt.save(update_fields=["status", "finished_at"])
    attempt.refresh_from_db()
    return attempt
