from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("webpush", "0005_auto_20230614_1529")]

    operations = [
        migrations.AlterField(
            model_name="subscriptioninfo",
            name="user_agent",
            field=models.CharField(max_length=500, blank=True),
        ),
    ]
