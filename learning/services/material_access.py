"""A subject and its descendants form one author-owned material collection."""


def material_subject(obj):
    label = obj._meta.model_name
    if label == "subject":
        return obj
    if label in {"workbook", "topic"}:
        return obj.subject
    if label == "unit":
        return obj.workbook.subject
    if label in {"task", "question"}:
        return obj.topic.subject
    if label in {"choice", "matchingpair", "questionimage"}:
        return obj.question.topic.subject
    raise ValueError(f"Unsupported material model: {label}")


def can_edit_material(user, obj):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    return user.is_superuser or (
        user.role == "teacher" and material_subject(obj).owner_id == user.pk
    )


def can_read_attempt_material(attempt):
    """Retain completed history; unfinished work requires a current assignment."""
    from learning.models import Attempt

    if attempt.status == Attempt.Status.COMPLETED:
        return True
    entry = attempt.schedule_entry
    return bool(
        entry and entry.group.is_active and entry.topic.is_active
        and entry.topic.subject.is_active and entry.task_id and entry.task.is_active
        and entry.task_id == attempt.task_id and entry.topic_id == attempt.topic_id
        and entry.group.students.filter(pk=attempt.student_id).exists()
    )


OWNER_LOOKUPS = {
    "subject": "owner_id", "workbook": "subject__owner_id",
    "unit": "workbook__subject__owner_id", "topic": "subject__owner_id",
    "task": "topic__subject__owner_id", "question": "topic__subject__owner_id",
}
