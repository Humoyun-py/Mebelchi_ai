from django.db import migrations

FLAGS = [("registration", "Allow new user registration"), ("chat", "Rule-based chat assistant"), ("optimizer", "Material optimizer"),
         ("exports", "PDF / Excel / 3D exports"), ("interior_designer", "Home owner interior designer")]


def seed(apps, schema_editor):
    F = apps.get_model("analytics", "FeatureFlag")
    for key, desc in FLAGS:
        F.objects.get_or_create(key=key, defaults=dict(description=desc, enabled=True))


class Migration(migrations.Migration):
    dependencies = [("analytics", "0002_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
