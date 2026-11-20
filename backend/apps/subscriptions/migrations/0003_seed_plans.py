from django.db import migrations

from apps.subscriptions.seed_data import PLANS


def seed(apps, schema_editor):
    P = apps.get_model("subscriptions", "Plan")
    for d in PLANS:
        d = dict(d)
        slug = d.pop("slug")
        P.objects.get_or_create(slug=slug, defaults=d)


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0002_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
