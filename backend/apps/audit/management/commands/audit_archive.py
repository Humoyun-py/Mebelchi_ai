"""Audit-log size report and archiving. Never deletes anything.

  manage.py audit_archive --report                         size, rows, oldest/newest; exit 1 with --fail-on-warn when over the threshold
  manage.py audit_archive --archive --out-dir DIR          copy rows older than --older-than-days (default AUDIT_ARCHIVE_AFTER_DAYS) to DIR
  manage.py audit_archive --verify --out-dir DIR           re-check every archive file against its manifest and the live table
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.audit import retention


class Command(BaseCommand):
    help = "Report on and archive (copy, never delete) the append-only audit log."

    def add_arguments(self, p):
        p.add_argument("--report", action="store_true")
        p.add_argument("--archive", action="store_true")
        p.add_argument("--verify", action="store_true")
        p.add_argument("--out-dir")
        p.add_argument("--older-than-days", type=int, default=None)
        p.add_argument("--file-rows", type=int, default=50_000)
        p.add_argument("--fail-on-warn", action="store_true")

    def handle(self, *a, report, archive, verify, out_dir, older_than_days, file_rows, fail_on_warn, **kw):
        if not (report or archive or verify):
            raise CommandError("Choose --report, --archive or --verify.")
        if (archive or verify) and not out_dir:
            raise CommandError("--out-dir is required for --archive and --verify.")
        alias = retention.archive_alias()
        if alias == "default":
            self.stderr.write("note: no audit_archiver database configured; reading with the application role "
                              "(set AUDIT_ARCHIVER_USER, see deploy/sql/audit_roles.sql)")
        failed = False
        if report:
            s = retention.table_stats(alias)
            size = f"{s['size_bytes'] / 1048576:.1f} MiB" if s["size_bytes"] is not None else "n/a (not PostgreSQL)"
            self.stdout.write(f"audit_auditlog: rows={s['rows']} size={size} oldest={s['oldest']} newest={s['newest']} last_id={s['last_id']}")
            if s["over_threshold"]:
                self.stdout.write(f"WARNING: larger than AUDIT_TABLE_WARN_MB={settings.AUDIT_TABLE_WARN_MB}. Archive old rows and plan the table shrink.")
                failed = fail_on_warn
        if archive:
            days = older_than_days or int(settings.AUDIT_ARCHIVE_AFTER_DAYS)
            made = retention.export_old_rows(Path(out_dir), days, file_rows, alias)
            total = sum(m["rows"] for m in made)
            self.stdout.write(f"archived {total} rows into {len(made)} file(s) in {out_dir}; nothing was deleted from the database")
        if verify:
            problems = retention.verify_archive(Path(out_dir), alias)
            for pr in problems:
                self.stderr.write(f"PROBLEM {pr}")
            self.stdout.write("archive verified: all files intact" if not problems else f"{len(problems)} problem(s) found")
            failed = failed or bool(problems)
        if failed:
            raise SystemExit(1)
