from learning.services.snapshots import question_snapshot
import secrets
import random
from django.db import transaction
from rest_framework.exceptions import ValidationError
from learning.models import AttemptQuestion


def ensure_matching_tokens(question):
    if question.matching_left_tokens and question.matching_right_tokens:
        return question
    with transaction.atomic():
        locked = AttemptQuestion.objects.select_for_update().get(pk=question.pk)
        if not locked.matching_left_tokens or not locked.matching_right_tokens:
            pair_ids = [pair["id"] for pair in question_snapshot(locked)["matching_pairs"]]
            locked.matching_left_tokens = {"L" + secrets.token_urlsafe(18): pk for pk in pair_ids}
            locked.matching_right_tokens = {"R" + secrets.token_urlsafe(18): pk for pk in pair_ids}
            if not locked.matching_left_order:
                locked.matching_left_order = random.sample(pair_ids, len(pair_ids))
            if not locked.matching_right_order:
                locked.matching_right_order = random.sample(pair_ids, len(pair_ids))
            locked.save(update_fields=["matching_left_tokens", "matching_right_tokens", "matching_left_order", "matching_right_order"])
        for field in ("matching_left_tokens", "matching_right_tokens", "matching_left_order", "matching_right_order"):
            setattr(question, field, getattr(locked, field))
    return question


def decode_matching(question, selection):
    ensure_matching_tokens(question)
    if not isinstance(selection, dict):
        raise ValidationError("Matching answer must be an object of opaque tokens.")
    result = {}
    right_seen = set()
    for left, right in selection.items():
        if not isinstance(left, str) or not isinstance(right, str):
            raise ValidationError("Matching tokens must be strings.")
        if left not in question.matching_left_tokens or right not in question.matching_right_tokens:
            raise ValidationError("Unknown matching token for this attempt question.")
        if right in right_seen:
            raise ValidationError("Each right-side value can only be used once.")
        right_seen.add(right)
        result[str(question.matching_left_tokens[left])] = question.matching_right_tokens[right]
    return result


def encode_matching(question, selection):
    ensure_matching_tokens(question)
    left = {str(pk): token for token, pk in question.matching_left_tokens.items()}
    right = {str(pk): token for token, pk in question.matching_right_tokens.items()}
    return {left[str(a)]: right[str(b)] for a, b in selection.items() if str(a) in left and str(b) in right}
