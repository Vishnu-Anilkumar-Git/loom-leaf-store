from django.db import migrations, models


def hide_legacy_categories(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Category.objects.filter(kind__in=("women", "kids")).update(is_active=False)


def restore_legacy_categories(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Category.objects.filter(kind__in=("women", "kids")).update(is_active=True)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="category",
            name="kind",
            field=models.CharField(
                choices=[
                    ("men", "Men"),
                    ("unisex", "Unisex"),
                    ("women", "Women (legacy)"),
                    ("kids", "Kids (legacy)"),
                ],
                max_length=10,
                unique=True,
            ),
        ),
        migrations.RunPython(hide_legacy_categories, restore_legacy_categories),
    ]
