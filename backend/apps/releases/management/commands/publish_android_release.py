from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.releases import services


class Command(BaseCommand):
    help = "Register a signed Android APK as a release (checksum and size are computed from the file). Add --publish to make it public."

    def add_arguments(self, p):
        p.add_argument("--apk", required=True)
        p.add_argument("--app-version", dest="app_version", required=True, help="version name, e.g. 1.0.0")
        p.add_argument("--code", required=True, type=int, help="Android versionCode (build number)")
        p.add_argument("--notes", default="")
        p.add_argument("--notes-file", default="")
        p.add_argument("--channel", default="production", choices=["production", "development"])
        p.add_argument("--publish", action="store_true")

    def handle(self, *a, **o):
        notes = Path(o["notes_file"]).read_text(encoding="utf-8") if o["notes_file"] else o["notes"]
        try:
            rel = services.register_apk(o["apk"], version_name=o["app_version"], version_code=o["code"], notes=notes, channel=o["channel"], publish=o["publish"])
        except services.ReleaseError as e:
            raise CommandError(str(e)) from e
        self.stdout.write(self.style.SUCCESS(f"{rel} registered ({rel.size_bytes} bytes)"))
        self.stdout.write(f"sha256 {rel.sha256}")
        self.stdout.write("published" if rel.is_published else "NOT published yet (use the admin action or --publish)")
