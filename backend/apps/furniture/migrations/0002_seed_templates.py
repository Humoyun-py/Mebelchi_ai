from django.db import migrations

from apps.furniture.seed_data import TEMPLATES


def seed(apps, schema_editor):
    T = apps.get_model("furniture", "FurnitureTemplate")
    for slug, cat, name, desc, defaults in TEMPLATES:
        T.objects.get_or_create(slug=slug, defaults=dict(category=cat, name=name, description=desc, defaults=defaults))


class Migration(migrations.Migration):
    dependencies = [("furniture", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
