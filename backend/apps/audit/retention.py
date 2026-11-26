"""Audit-log retention: measure the table, and export old rows to verifiable files.

Nothing in here deletes or changes an audit row, and nothing may be added that does. The table is append-only on purpose (model layer,
and on PostgreSQL a trigger, migration 0004). "Archiving" therefore means *copying* old rows out to compressed JSON-lines files with a
manifest (row count, id range, SHA-256) so they can be kept off the database host. Shrinking the table afterwards is a deliberate
operator step with a superuser, after `--verify`; see docs/DEPLOYMENT.md ("Audit log retention").

Archiving reads through the optional `audit_archiver` database alias (a PostgreSQL role that has SELECT on the audit table and nothing
else, see deploy/sql/audit_roles.sql). When that alias is not configured the default connection is used.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import connections
from django.db.models import Max, Min
from django.utils import timezone

from .models import AuditLog

MANIFEST_GLOB = "audit-*.manifest.json"
FIELDS = ("id", "created_at", "actor_id", "actor_email", "action", "event", "model", "object_id", "object_repr", "changes", "ip", "method", "path")


def archive_alias() -> str:
    return "audit_archiver" if "audit_archiver" in connections.databases else "default"


def table_stats(using: str = "default") -> dict:
    qs = AuditLog.objects.using(using)
    agg = qs.aggregate(oldest=Min("created_at"), newest=Max("created_at"), last_id=Max("id"))
    size = None
    conn = connections[using]
    if conn.vendor == "postgresql":
        with conn.cursor() as cur:
            cur.execute("SELECT pg_total_relation_size(%s)", [AuditLog._meta.db_table])
            size = cur.fetchone()[0]
    warn_bytes = int(settings.AUDIT_TABLE_WARN_MB) * 1024 * 1024
    return {"rows": qs.count(), "oldest": agg["oldest"], "newest": agg["newest"], "last_id": agg["last_id"], "size_bytes": size,
            "warn_bytes": warn_bytes, "over_threshold": size is not None and size > warn_bytes}


def read_manifests(out_dir: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(Path(out_dir).glob(MANIFEST_GLOB))]


def last_archived_id(out_dir: Path) -> int:
    return max((m["last_id"] for m in read_manifests(out_dir)), default=0)


def _line(row: AuditLog) -> str:
    d = {f: getattr(row, f) for f in FIELDS}
    d["created_at"] = row.created_at.isoformat()
    return json.dumps(d, ensure_ascii=False, sort_keys=True, default=str)


def export_old_rows(out_dir: Path, older_than_days: int, file_rows: int = 50_000, using: str | None = None) -> list[dict]:
    """Writes every audit row older than the cutoff that is not archived yet, `file_rows` per file, and returns the new manifests.

    Archiving continues after the highest id already in a manifest, and only takes a contiguous run of rows (it stops at the first row
    that is newer than the cutoff), so a re-run never skips or repeats a row. Existing files are never overwritten."""
    if older_than_days < 1 or file_rows < 1:
        raise ValueError("older_than_days and file_rows must be at least 1")
    using = using or archive_alias()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cutoff = timezone.now() - timedelta(days=older_than_days)
    after = last_archived_id(out)
    done: list[dict] = []
    rows = AuditLog.objects.using(using).filter(id__gt=after).order_by("id").iterator(chunk_size=2000)
    batch: list[AuditLog] = []
    for row in rows:
        if row.created_at >= cutoff:
            break
        batch.append(row)
        if len(batch) == file_rows:
            done.append(_write(out, batch, cutoff))
            batch = []
    if batch:
        done.append(_write(out, batch, cutoff))
    return done


def _write(out: Path, batch: list[AuditLog], cutoff) -> dict:
    first, last = batch[0].id, batch[-1].id
    name = f"audit-{first:012d}-{last:012d}.jsonl.gz"
    final = out / name
    if final.exists():
        raise FileExistsError(f"{final} already exists; refusing to overwrite an archive file")
    tmp = out / (name + ".tmp")
    digest = hashlib.sha256()
    with open(tmp, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
        for row in batch:
            gz.write((_line(row) + "\n").encode())
    digest.update(tmp.read_bytes())
    os.replace(tmp, final)
    manifest = {"file": name, "rows": len(batch), "first_id": first, "last_id": last, "oldest": batch[0].created_at.isoformat(),
                "newest": batch[-1].created_at.isoformat(), "cutoff": cutoff.isoformat(), "sha256": digest.hexdigest(),
                "written_at": timezone.now().isoformat()}
    mtmp = out / (name.replace(".jsonl.gz", ".manifest.json") + ".tmp")
    mtmp.write_text(json.dumps(manifest, indent=2))
    os.replace(mtmp, out / name.replace(".jsonl.gz", ".manifest.json"))
    return manifest


def verify_archive(out_dir: Path, using: str | None = None) -> list[str]:
    """Returns a list of problems (empty = every file is intact). Checks existence, SHA-256, row count, id order, and that each
    archived row still exists in the database with the same content (a mismatch would mean the live table was tampered with)."""
    using = using or archive_alias()
    out = Path(out_dir)
    problems: list[str] = []
    for m in read_manifests(out):
        f = out / m["file"]
        if not f.exists():
            problems.append(f"{m['file']}: file is missing")
            continue
        if hashlib.sha256(f.read_bytes()).hexdigest() != m["sha256"]:
            problems.append(f"{m['file']}: checksum mismatch")
            continue
        ids = []
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                rec = json.loads(line)
                ids.append(rec["id"])
        if len(ids) != m["rows"] or ids != sorted(ids) or (ids and (ids[0], ids[-1]) != (m["first_id"], m["last_id"])):
            problems.append(f"{m['file']}: row count or id range does not match the manifest")
            continue
        live = AuditLog.objects.using(using).filter(id__in=ids).count()
        if live and live != len(ids):
            problems.append(f"{m['file']}: {len(ids) - live} archived rows are no longer in the table (live table changed)")
    return problems
