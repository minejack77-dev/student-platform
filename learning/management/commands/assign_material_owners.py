import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from accounts.models import User
from learning.models import Subject


class Command(BaseCommand):
    help = "Assign reviewed owners to legacy subjects; dry run unless --apply is supplied."

    def add_arguments(self, parser):
        parser.add_argument("--mapping", required=True, help="JSON object mapping subject IDs to teacher user IDs")
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            mapping = json.loads(Path(options["mapping"]).read_text(encoding="utf-8"))
            if not isinstance(mapping, dict):
                raise ValueError
            pairs = [(int(subject), int(user)) for subject, user in mapping.items()]
        except (OSError, ValueError, TypeError):
            raise CommandError("Provide a JSON object with numeric subject and user IDs.")
        if len({subject for subject, _ in pairs}) != len(pairs):
            raise CommandError("Duplicate subject IDs.")
        subjects = {s.pk: s for s in Subject.objects.select_for_update().filter(pk__in=[s for s, _ in pairs])}
        users = set(User.objects.filter(pk__in=[u for _, u in pairs], role="teacher", is_active=True, teacher_profile__isnull=False).values_list("pk", flat=True))
        for subject_id, user_id in pairs:
            subject = subjects.get(subject_id)
            if subject is None or user_id not in users:
                raise CommandError("Every mapping must name an existing subject and active teacher.")
            if subject.owner_id not in (None, user_id):
                raise CommandError("An existing owner cannot be replaced by this command.")
        if options["apply"]:
            for subject_id, user_id in pairs:
                Subject.objects.filter(pk=subject_id).update(owner_id=user_id)
        self.stdout.write(f"{'Applied' if options['apply'] else 'Dry run'}: {len(pairs)} reviewed subject mappings.")
