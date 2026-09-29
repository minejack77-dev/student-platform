"""Transactional, repeatable spreadsheet import with a signed undo receipt."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core import signing
from django.db import transaction
from rest_framework.exceptions import ValidationError, PermissionDenied
from learning.services.material_access import can_edit_material

from learning.models import AttemptQuestion, Question, Task
from learning.services.question_import import import_questions_from_xls
from learning.services.question_import import MAX_UPLOAD_BYTES


def fingerprint(question):
    content = [question.text, question.instruction, question.question_type, question.is_active,
               list(question.choices.order_by('order', 'id').values_list('text', 'is_correct', 'order')),
               list(question.matching_pairs.order_by('order', 'id').values_list('left_content', 'right_content', 'order'))]
    return hashlib.sha256(json.dumps(content, ensure_ascii=False).encode()).hexdigest()


@transaction.atomic
def import_batch(*, task, upload, user, preview=False, **options):
    task = Task.objects.select_for_update().get(pk=task.pk)
    if not can_edit_material(user, task):
        raise PermissionDenied("Only the material owner can import questions.")
    seen = {fingerprint(q) for q in task.questions.prefetch_related('choices', 'matching_pairs')}
    suffix = Path(upload.name).suffix.lower()
    if suffix not in ('.xls', '.xlsx'):
        raise ValidationError({'code': 'invalid_file'})
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError({'code': 'invalid_file'})
    with TemporaryDirectory() as directory:
        source = Path(directory) / ('questions' + suffix)
        with source.open('wb') as stream:
            total = 0
            for chunk in upload.chunks():
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise ValidationError({'code': 'invalid_file'})
                stream.write(chunk)
        imported = import_questions_from_xls(task=task, src=source, **options)
    kept, duplicates, receipt = [], 0, {}
    for question in imported:
        digest = fingerprint(question)
        if digest in seen:
            question.delete()
            duplicates += 1
        else:
            seen.add(digest)
            kept.append(question)
            receipt[str(question.id)] = digest
    result = {'imported_count': len(kept), 'duplicate_count': duplicates,
              'preview': preview, 'questions': [q.text for q in kept[:10]]}
    if preview:
        transaction.set_rollback(True)
    elif receipt:
        result['undo_token'] = signing.dumps({'task': task.id, 'user': user.id, 'questions': receipt}, salt='question-import')
    return result


@transaction.atomic
def undo_batch(*, task, user, token):
    if not can_edit_material(user, task):
        raise PermissionDenied("Only the material owner can undo imports.")
    try:
        receipt = signing.loads(token, salt='question-import', max_age=86400)
    except (signing.BadSignature, TypeError):
        raise ValidationError({'code': 'protected_import'})
    if receipt.get('task') != task.id or receipt.get('user') != user.id:
        raise ValidationError({'code': 'protected_import'})
    Task.objects.select_for_update().get(pk=task.pk)
    questions = list(Question.objects.select_for_update().filter(task=task, id__in=receipt['questions']))
    if len(questions) != len(receipt['questions']) or AttemptQuestion.objects.filter(question__in=questions).exists():
        raise ValidationError({'code': 'protected_import'})
    if any(fingerprint(q) != receipt['questions'][str(q.id)] for q in questions):
        raise ValidationError({'code': 'protected_import'})
    count = len(questions)
    Question.objects.filter(id__in=[q.id for q in questions]).delete()
    return count
