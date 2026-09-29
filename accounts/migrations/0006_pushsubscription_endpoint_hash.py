from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_pushsubscription")]
    operations = [migrations.AddField(
        model_name="pushsubscription", name="endpoint_hash",
        field=models.CharField(blank=True, max_length=64, null=True, unique=True),
    )]
