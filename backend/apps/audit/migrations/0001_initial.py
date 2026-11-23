from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("actor_id", models.BigIntegerField(blank=True, null=True)),
                ("actor_email", models.CharField(blank=True, max_length=254)),
                ("action", models.CharField(max_length=60)),
                ("target_type", models.CharField(max_length=40)),
                ("target_id", models.CharField(max_length=64)),
                ("changes", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
