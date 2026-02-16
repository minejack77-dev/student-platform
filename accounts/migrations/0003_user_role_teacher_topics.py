from django.db import migrations, models


def sync_user_roles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Student = apps.get_model("accounts", "Student")
    Teacher = apps.get_model("accounts", "Teacher")

    teacher_user_ids = set(Teacher.objects.values_list("user_id", flat=True))
    student_user_ids = set(Student.objects.values_list("user_id", flat=True))

    for user in User.objects.all().only("id", "role"):
        if user.id in teacher_user_ids:
            expected_role = "teacher"
        elif user.id in student_user_ids:
            expected_role = "student"
        else:
            expected_role = "student"

        if user.role != expected_role:
            user.role = expected_role
            user.save(update_fields=["role"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_remove_user_role_student_teacher"),
        ("learning", "0005_groupstudent_group_students_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[("student", "Student"), ("teacher", "Teacher")],
                db_index=True,
                default="student",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="teacher",
            name="topics",
            field=models.ManyToManyField(
                blank=True, related_name="teachers", to="learning.topic"
            ),
        ),
        migrations.RunPython(sync_user_roles, noop_reverse),
    ]
