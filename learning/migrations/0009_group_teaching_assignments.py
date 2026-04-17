import django.db.models.deletion
from django.db import migrations, models


def migrate_group_subject_topic_to_teacher_assignments(apps, schema_editor):
    Group = apps.get_model("learning", "Group")
    GroupTeachingAssignment = apps.get_model("learning", "GroupTeachingAssignment")

    groups = Group.objects.exclude(subject__isnull=True).exclude(teacher__isnull=True)
    for group in groups.iterator():
        GroupTeachingAssignment.objects.update_or_create(
            group_id=group.id,
            teacher_id=group.teacher_id,
            defaults={
                "subject_id": group.subject_id,
                "topic_id": group.topic_id,
            },
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("learning", "0008_subject_and_group_topic_assignment"),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupTeachingAssignment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="teaching_assignments",
                        to="learning.group",
                    ),
                ),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="teaching_assignments",
                        to="learning.subject",
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_assignments",
                        to="accounts.teacher",
                    ),
                ),
                (
                    "topic",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="teaching_assignments",
                        to="learning.topic",
                    ),
                ),
            ],
            options={
                "ordering": ["group__name", "teacher__user__username"],
            },
        ),
        migrations.AddConstraint(
            model_name="groupteachingassignment",
            constraint=models.UniqueConstraint(
                fields=("group", "teacher"),
                name="uq_group_teacher_assignment",
            ),
        ),
        migrations.RunPython(
            migrate_group_subject_topic_to_teacher_assignments,
            noop_reverse,
        ),
        migrations.RemoveField(
            model_name="group",
            name="subject",
        ),
        migrations.RemoveField(
            model_name="group",
            name="topic",
        ),
    ]
