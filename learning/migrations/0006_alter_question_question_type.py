from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("learning", "0005_groupstudent_group_students_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="question",
            name="question_type",
            field=models.CharField(
                choices=[
                    ("single_choice", "Single choice"),
                    ("multiple_choice", "Multiple choice"),
                ],
                default="multiple_choice",
                max_length=30,
            ),
        ),
    ]
