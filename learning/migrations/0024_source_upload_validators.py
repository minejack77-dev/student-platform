from django.db import migrations, models
import learning.services.uploads


class Migration(migrations.Migration):
    dependencies = [("learning", "0023_attemptquestion_matching_tokens")]
    operations = [migrations.AlterField(
        model_name=model, name="src", field=models.FileField(blank=True, null=True, validators=[learning.services.uploads.validate_source_upload]),
    ) for model in ("topic", "task")]
