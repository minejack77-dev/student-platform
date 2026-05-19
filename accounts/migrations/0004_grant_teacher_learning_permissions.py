from django.db import migrations


TEACHER_API_MODELS = (
    "subject",
    "workbook",
    "unit",
    "topic",
    "task",
    "question",
    "group",
)


def grant_teacher_learning_permissions(apps, schema_editor):
    Teacher = apps.get_model("accounts", "Teacher")
    Permission = apps.get_model("auth", "Permission")

    codenames = [
        f"{action}_{model_name}"
        for model_name in TEACHER_API_MODELS
        for action in ("view", "add", "change", "delete")
    ]
    permissions = Permission.objects.filter(
        content_type__app_label="learning",
        codename__in=codenames,
    )

    for teacher in Teacher.objects.select_related("user"):
        teacher.user.user_permissions.add(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_user_role_teacher_topics"),
        ("learning", "0017_task_attempt_settings"),
    ]

    operations = [
        migrations.RunPython(
            grant_teacher_learning_permissions,
            migrations.RunPython.noop,
        ),
    ]
