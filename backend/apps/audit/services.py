from .models import AuditLog


def record(action: str, *, actor=None, target_type: str, target_id, changes: dict | None = None) -> AuditLog:
    """Append one audit entry. Call inside the same transaction as the change it describes."""
    return AuditLog.objects.create(
        actor_id=getattr(actor, "id", None),
        actor_email=(getattr(actor, "email", "") or "")[:254],
        action=action[:60],
        target_type=target_type[:40],
        target_id=str(target_id)[:64],
        changes=changes or {},
    )
