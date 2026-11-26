import gzip
import io
import json
import tempfile
from datetime import timedelta
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.audit import retention, services
from apps.audit.models import AppendOnlyError, AuditLog
from apps.audit.tasks import check_audit_size




def old_rows(n, days_old, start=0):
    """Creates rows that are already `days_old` days old. bulk_create does not call the guarded save(), and `created_at` of an
    auto_now_add field is set in pre_save, so patch it through a custom value after objects are built."""
    when = timezone.now() - timedelta(days=days_old)
    objs = [AuditLog(action="create", event=f"old.event{start + i}", model="x.thing", object_id=str(start + i), actor_email="a@x.com", changes={"k": [1, 2]}) for i in range(n)]
    for o in objs:
        o.created_at = when
    # auto_now_add overwrites on insert; disable it for this insert only
    field = AuditLog._meta.get_field("created_at")
    field.auto_now_add = False
    try:
        AuditLog.objects.bulk_create(objs)
    finally:
        field.auto_now_add = True
    return objs


class ExportTests(TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp())

    def test_old_rows_are_copied_and_nothing_is_deleted(self):
        old_rows(7, 400)
        services.record("recent.event", target_type="thing", target_id=1)
        before = AuditLog.objects.count()
        made = retention.export_old_rows(self.out, 365, file_rows=3)
        self.assertEqual([m["rows"] for m in made], [3, 3, 1])
        self.assertEqual(AuditLog.objects.count(), before)                      # no row was removed
        with gzip.open(self.out / made[0]["file"], "rt") as f:
            first = json.loads(f.readline())
        self.assertEqual((first["event"], first["model"], first["changes"], first["actor_email"]), ("old.event0", "x.thing", {"k": [1, 2]}, "a@x.com"))
        self.assertFalse(any("recent.event" in (self.out / m["file"]).read_bytes().decode("latin1") for m in made))

    def test_recent_rows_are_never_exported(self):
        services.record("recent.event", target_type="thing", target_id=1)
        self.assertEqual(retention.export_old_rows(self.out, 365), [])

    def test_a_rerun_continues_after_the_last_archived_row_without_repeats(self):
        old_rows(4, 400)
        first = retention.export_old_rows(self.out, 365)
        self.assertEqual(sum(m["rows"] for m in first), 4)
        self.assertEqual(retention.export_old_rows(self.out, 365), [])           # nothing new
        old_rows(2, 400, start=100)
        second = retention.export_old_rows(self.out, 365)
        self.assertEqual(sum(m["rows"] for m in second), 2)
        self.assertEqual(second[0]["first_id"], first[-1]["last_id"] + 1)
        self.assertEqual(retention.verify_archive(self.out), [])

    def test_existing_archive_files_are_never_overwritten(self):
        old_rows(2, 400)
        m = retention.export_old_rows(self.out, 365)[0]
        (self.out / m["file"].replace(".jsonl.gz", ".manifest.json")).unlink()   # forget the manifest: the data file must still be protected
        with self.assertRaises(FileExistsError):
            retention.export_old_rows(self.out, 365)

    def test_invalid_arguments(self):
        for kw in ({"older_than_days": 0}, {"older_than_days": 5, "file_rows": 0}):
            with self.assertRaises(ValueError):
                retention.export_old_rows(self.out, **kw)


class VerifyTests(TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp())
        old_rows(5, 400)
        self.m = retention.export_old_rows(self.out, 365)[0]

    def test_intact_archive_passes(self):
        self.assertEqual(retention.verify_archive(self.out), [])

    def test_tampering_missing_files_and_changed_manifests_are_found(self):
        f = self.out / self.m["file"]
        raw = f.read_bytes()
        f.write_bytes(raw[:-5] + b"XXXXX")
        self.assertIn("checksum mismatch", retention.verify_archive(self.out)[0])
        f.unlink()
        self.assertIn("file is missing", retention.verify_archive(self.out)[0])

    def test_a_manifest_that_lies_about_the_row_count_is_found(self):
        mp = self.out / self.m["file"].replace(".jsonl.gz", ".manifest.json")
        data = json.loads(mp.read_text()); data["rows"] = 99; mp.write_text(json.dumps(data))
        self.assertIn("row count", retention.verify_archive(self.out)[0])


class StatsAndCommandTests(TestCase):
    def test_stats_and_threshold(self):
        old_rows(3, 10)
        s = retention.table_stats()
        self.assertEqual(s["rows"], AuditLog.objects.count())
        self.assertGreaterEqual(s["rows"], 3)
        self.assertFalse(s["over_threshold"])

    def test_the_daily_task_logs_only_above_the_threshold(self):
        with self.assertNoLogs("mebelchi.audit", "WARNING"):
            self.assertFalse(check_audit_size()["over_threshold"])

    def test_command_report_archive_verify(self):
        old_rows(3, 400)
        out = tempfile.mkdtemp(); buf = io.StringIO()
        call_command("audit_archive", "--report", stdout=buf, stderr=io.StringIO())
        self.assertIn("audit_auditlog: rows=", buf.getvalue())
        buf = io.StringIO(); call_command("audit_archive", "--archive", "--out-dir", out, "--older-than-days", "365", stdout=buf, stderr=io.StringIO())
        self.assertIn("archived 3 rows", buf.getvalue()); self.assertIn("nothing was deleted", buf.getvalue())
        buf = io.StringIO(); call_command("audit_archive", "--verify", "--out-dir", out, stdout=buf, stderr=io.StringIO())
        self.assertIn("all files intact", buf.getvalue())

    def test_command_needs_a_mode_and_an_out_dir(self):
        with self.assertRaises(CommandError):
            call_command("audit_archive")
        with self.assertRaises(CommandError):
            call_command("audit_archive", "--archive")

    def test_verify_exits_non_zero_when_the_archive_is_damaged(self):
        old_rows(2, 400); out = Path(tempfile.mkdtemp())
        m = retention.export_old_rows(out, 365)[0]
        (out / m["file"]).write_bytes(b"damaged")
        with self.assertRaises(SystemExit) as ctx:
            call_command("audit_archive", "--verify", "--out-dir", str(out), stdout=io.StringIO(), stderr=io.StringIO())
        self.assertEqual(ctx.exception.code, 1)

    @override_settings(AUDIT_TABLE_WARN_MB=0)
    def test_over_threshold_is_only_reported_on_postgresql(self):
        s = retention.table_stats()
        self.assertEqual(s["over_threshold"], s["size_bytes"] is not None)

    def test_archiving_does_not_open_a_way_to_delete(self):
        old_rows(2, 400)
        retention.export_old_rows(Path(tempfile.mkdtemp()), 365)
        with self.assertRaises(AppendOnlyError):
            AuditLog.objects.all().delete()
        with self.assertRaises(AppendOnlyError):
            AuditLog.objects.all().update(event="x")
