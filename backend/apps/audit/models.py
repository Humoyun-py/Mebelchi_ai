from django.db import models


class AppendOnlyError(RuntimeError):
    pass


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise AppendOnlyError("audit log rows cannot be updated")

    def delete(self):
        raise AppendOnlyError("audit log rows cannot be deleted")


class AuditLog(models.Model):
    """Who changed what. Rows are never edited or deleted by the application.

    The actor is stored as a plain ID and e-mail snapshot, not a foreign key, so that deleting an account
    never rewrites its history. PostgreSQL also enforces append-only with a trigger (see migration 0002).
    """

    actor_id = models.BigIntegerField(null=True, blank=True)
    actor_email = models.CharField(max_length=254, blank=True)
    action = models.CharField(max_length=60)
    target_type = models.CharField(max_length=40)
    target_id = models.CharField(max_length=64)
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AppendOnlyError("audit log rows cannot be updated")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnlyError("audit log rows cannot be deleted")
