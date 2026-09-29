from django.db import migrations, models


def measure_existing_images(apps, schema_editor):
    Image = apps.get_model("learning", "QuestionImage")
    for image in Image.objects.using(schema_editor.connection.alias).iterator(chunk_size=200):
        try:
            size = image.image.size if image.image else 0
        except FileNotFoundError:
            size = 0
        Image.objects.using(schema_editor.connection.alias).filter(pk=image.pk).update(size_bytes=size)


class Migration(migrations.Migration):
    dependencies = [("learning", "0024_source_upload_validators")]
    operations = [
        migrations.AddField(model_name="questionimage", name="size_bytes", field=models.PositiveIntegerField(default=0)),
        migrations.RunPython(measure_existing_images, migrations.RunPython.noop),
    ]
