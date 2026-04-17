import django.db.models.deletion
from django.db import migrations, models


def assign_default_subject(apps, schema_editor):
    Subject = apps.get_model("learning", "Subject")
    Topic = apps.get_model("learning", "Topic")

    default_subject, _ = Subject.objects.get_or_create(
        name="General",
        defaults={"description": "Auto-created subject for existing topics."},
    )
    Topic.objects.filter(subject__isnull=True).update(subject=default_subject)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("learning", "0007_topic_group_updated_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="Subject",
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
                ("name", models.CharField(max_length=200, unique=True)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="group",
            name="subject",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="groups",
                to="learning.subject",
            ),
        ),
        migrations.AddField(
            model_name="group",
            name="topic",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="groups",
                to="learning.topic",
            ),
        ),
        migrations.AddField(
            model_name="topic",
            name="subject",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="topics",
                to="learning.subject",
            ),
        ),
        migrations.RunPython(assign_default_subject, noop_reverse),
        migrations.AlterField(
            model_name="topic",
            name="subject",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="topics",
                to="learning.subject",
            ),
        ),
        migrations.AlterField(
            model_name="topic",
            name="title",
            field=models.CharField(max_length=200),
        ),
        migrations.AddConstraint(
            model_name="topic",
            constraint=models.UniqueConstraint(
                fields=("subject", "title"),
                name="uq_topic_subject_title",
            ),
        ),
    ]
