from django.db import migrations, models
import django.db.models.deletion


def populate_assignment_workbooks(apps, schema_editor):
    GroupTeachingAssignment = apps.get_model("learning", "GroupTeachingAssignment")

    for assignment in GroupTeachingAssignment.objects.select_related(
        "topic__unit__workbook",
        "task__topic__unit__workbook",
    ):
        workbook_id = None
        if assignment.topic_id and assignment.topic and assignment.topic.unit_id:
            workbook_id = assignment.topic.unit.workbook_id
        elif assignment.task_id and assignment.task and assignment.task.topic_id:
            workbook_id = assignment.task.topic.unit.workbook_id

        if workbook_id and assignment.workbook_id != workbook_id:
            assignment.workbook_id = workbook_id
            assignment.save(update_fields=["workbook"])


class Migration(migrations.Migration):

    dependencies = [
        ("learning", "0017_task_attempt_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="groupteachingassignment",
            name="workbook",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="teaching_assignments",
                to="learning.workbook",
            ),
        ),
        migrations.RunPython(
            populate_assignment_workbooks,
            migrations.RunPython.noop,
        ),
    ]
