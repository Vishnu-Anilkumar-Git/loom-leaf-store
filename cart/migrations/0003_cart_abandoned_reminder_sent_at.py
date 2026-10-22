from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cart", "0002_initial")]

    operations = [
        migrations.AddField(
            model_name="cart",
            name="abandoned_reminder_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
