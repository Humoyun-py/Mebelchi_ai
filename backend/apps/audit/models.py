from django.conf import settings
from django.db import models


class AppendOnlyError(PermissionError):
    """Raised when code tries to change or delete an audit row."""


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise AppendOnlyError("audit log rows cannot be updated")

    def delete(self):
        raise AppendOnlyError("audit log rows cannot be deleted")

    def bulk_update(self, *args, **kwargs):
        raise AppendOnlyError("audit log rows cannot be updated")


class AuditLog(models.Model):
    """Append-only record of who did what to which object. The application never updates or deletes rows, and on PostgreSQL a
    trigger (migration 0004) refuses UPDATE, DELETE and TRUNCATE even for raw SQL.

    `actor` is a foreign key *without* a database constraint and with DO_NOTHING: deleting an account must never rewrite history
    (that would be an UPDATE), so the id stays and `actor_email` is the readable snapshot."""

    class Action(models.TextChoices):
        CREATE = "create", "Created"
        UPDATE = "update", "Updated"
        DELETE = "delete", "Deleted"
        LOGIN = "login", "Logged in"
        LOGOUT = "logout", "Logged out"
        PASSWORD = "password", "Password changed"

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.DO_NOTHING, db_constraint=False, related_name="+")
    actor_email = models.CharField(max_length=254, blank=True, help_text="Kept even if the account is deleted later; empty for system actions.")
    action = models.CharField(max_length=10, choices=Action.choices)
    event = models.CharField(max_length=40, blank=True, db_index=True,
                             help_text="Business event name, e.g. order.status_changed; empty for plain create/update/delete")
    model = models.CharField(max_length=80, blank=True, help_text="app_label.model")
    object_id = models.CharField(max_length=64, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    changes = models.JSONField(default=dict, blank=True, help_text="{field: {old, new}} for updates; sensitive values are redacted")
    ip = models.GenericIPAddressField(null=True, blank=True)
    method = models.CharField(max_length=8, blank=True)
    path = models.CharField(max_length=255, blank=True)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["model", "object_id"], name="audit_object_idx"),
            models.Index(fields=["actor", "-created_at"], name="audit_actor_idx"),
            models.Index(fields=["action", "-created_at"], name="audit_action_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise AppendOnlyError("Audit log entries are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnlyError("Audit log entries cannot be deleted.")

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor_email or 'system'} {self.action} {self.model}#{self.object_id}"
