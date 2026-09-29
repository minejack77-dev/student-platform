from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("learning", "0022_subject_owner")]
    operations = [
        migrations.AddField(model_name="attemptquestion", name="matching_left_tokens", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="attemptquestion", name="matching_right_tokens", field=models.JSONField(blank=True, default=dict)),
    ]
