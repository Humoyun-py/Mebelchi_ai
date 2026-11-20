from decimal import Decimal

from django.db import migrations

from apps.materials.seed_data import SYSTEM_MATERIALS


def seed(apps, schema_editor):
    M = apps.get_model("materials", "Material")
    for name, kind, t, l, w, color in SYSTEM_MATERIALS:
        M.objects.get_or_create(name=name, is_system=True, defaults=dict(kind=kind, thickness=Decimal(t), sheet_length=l, sheet_width=w, color=color))


class Migration(migrations.Migration):
    dependencies = [("materials", "0002_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
