import logging

from celery import shared_task

from . import retention

logger = logging.getLogger("mebelchi.audit")


@shared_task
def check_audit_size() -> dict:
    """Daily size check of the append-only audit table. Logs a WARNING above AUDIT_TABLE_WARN_MB (the operator then archives, see
    docs/DEPLOYMENT.md). Reads only."""
    s = retention.table_stats(retention.archive_alias())
    if s["over_threshold"]:
        logger.warning("audit_auditlog is %.0f MiB (%d rows), above the %d MiB threshold: archive old rows",
                       s["size_bytes"] / 1048576, s["rows"], s["warn_bytes"] // 1048576)
    return {"rows": s["rows"], "size_bytes": s["size_bytes"], "over_threshold": s["over_threshold"]}
