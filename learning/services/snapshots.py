"""Attempt content is independent of subsequent edits to the question bank."""


def capture_question(question, *, legacy=False):
    return {
        "id": question.pk, "topic": question.topic_id, "task": question.task_id,
        "text": question.text, "instruction": question.instruction,
        "question_type": question.question_type, "is_active": question.is_active,
        "created_at": question.created_at.isoformat(),
        "choices": list(question.choices.values("id", "text", "order", "is_correct")),
        "matching_pairs": list(question.matching_pairs.values("id", "left_content", "right_content", "order")),
        "images": list(question.images.values("id", "image", "original_name", "order")),
        "provenance": "legacy_current_content_not_verified" if legacy else "captured_at_start",
    }


def question_snapshot(attempt_question):
    # The fallback is for pre-migration/in-memory objects only; migration backfills rows.
    return attempt_question.content_snapshot or capture_question(attempt_question.question, legacy=True)
