import hashlib
import io
import tempfile
import zipfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.releases import services
from apps.releases.models import AppRelease


def make_apk(path: Path, payload: bytes = b"code", with_manifest=True, with_dex=True) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        if with_manifest:
            z.writestr("AndroidManifest.xml", b"manifest")
        if with_dex:
            z.writestr("classes.dex", payload)
    return path


class ReleaseBase(TestCase):
    def setUp(self):
        self._media = tempfile.TemporaryDirectory()
        self.addCleanup(self._media.cleanup)
        self._ov = override_settings(MEDIA_ROOT=self._media.name)
        self._ov.enable()
        self.addCleanup(self._ov.disable)
        self._src = tempfile.TemporaryDirectory()
        self.addCleanup(self._src.cleanup)
        self.client = APIClient()

    def apk(self, name="a.apk", **kw) -> Path:
        return make_apk(Path(self._src.name) / name, **kw)

    def register(self, version="1.0.0", code=1, publish=False, **kw):
        return services.register_apk(self.apk(f"{code}.apk", payload=f"build {code}".encode()), version_name=version, version_code=code, publish=publish, **kw)


class RegisterTests(ReleaseBase):
    def test_checksum_and_size_come_from_the_file(self):
        src = self.apk()
        rel = services.register_apk(src, version_name="1.2.3", version_code=7, notes="  Fixes  ")
        self.assertEqual(rel.sha256, hashlib.sha256(src.read_bytes()).hexdigest())
        self.assertEqual(rel.size_bytes, src.stat().st_size)
        self.assertEqual(rel.notes, "Fixes")
        self.assertFalse(rel.is_published)
        self.assertEqual(hashlib.sha256(Path(rel.apk.path).read_bytes()).hexdigest(), rel.sha256)

    def test_rejects_files_that_are_not_apks(self):
        bad = Path(self._src.name) / "x.apk"
        bad.write_bytes(b"not a zip")
        with self.assertRaisesMessage(services.ReleaseError, "not a valid APK"):
            services.register_apk(bad, version_name="1.0.0", version_code=1)
        with self.assertRaisesMessage(services.ReleaseError, "not an Android app"):
            services.register_apk(self.apk("n.apk", with_manifest=False), version_name="1.0.0", version_code=1)
        with self.assertRaisesMessage(services.ReleaseError, "not an Android app"):
            services.register_apk(self.apk("d.apk", with_dex=False), version_name="1.0.0", version_code=1)
        with self.assertRaises(services.ReleaseError):
            services.register_apk(Path(self._src.name) / "missing.apk", version_name="1.0.0", version_code=1)
        self.assertEqual(AppRelease.objects.count(), 0)

    def test_rejects_bad_versions_and_duplicate_codes(self):
        for v in ("1.0", "v1.0.0", "1.0.0; rm", ""):
            with self.assertRaises(services.ReleaseError, msg=v):
                services.register_apk(self.apk(), version_name=v, version_code=1)
        for c in (0, -1, True, "3"):
            with self.assertRaises(services.ReleaseError, msg=str(c)):
                services.register_apk(self.apk(), version_name="1.0.0", version_code=c)
        self.register(code=1)
        with self.assertRaisesMessage(services.ReleaseError, "already exists"):
            self.register(version="1.0.1", code=1)

    def test_same_code_may_exist_in_the_development_channel(self):
        self.register(code=1)
        dev = self.register(code=1, channel="development")
        self.assertEqual(dev.channel, "development")

    def test_a_lower_code_cannot_be_published_after_a_higher_one(self):
        self.register(version="1.1.0", code=5, publish=True)
        low = self.register(version="1.0.0", code=3)
        with self.assertRaisesMessage(services.ReleaseError, "higher code"):
            services.publish_release(low)
        low.refresh_from_db()
        self.assertFalse(low.is_published)

    def test_development_builds_cannot_be_published(self):
        dev = self.register(code=2, channel="development")
        with self.assertRaisesMessage(services.ReleaseError, "Only production"):
            services.publish_release(dev)


class PublicApiTests(ReleaseBase):
    def test_nothing_is_listed_until_published(self):
        self.register(code=1)
        r = self.client.get("/api/v1/app/android/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"latest": None, "releases": []})
        self.assertEqual(self.client.get("/api/v1/app/android/latest/download/").status_code, 404)

    def test_latest_and_history_are_newest_first_and_hide_development_builds(self):
        self.register(version="1.0.0", code=1, publish=True, notes="first")
        self.register(version="1.1.0", code=2, publish=True, notes="second")
        self.register(version="9.9.9", code=3)  # not published
        self.register(version="2.0.0", code=9, channel="development")
        d = self.client.get("/api/v1/app/android/").json()
        self.assertEqual(d["latest"]["version_name"], "1.1.0")
        self.assertEqual([x["version_code"] for x in d["releases"]], [2, 1])
        self.assertEqual(d["latest"]["notes"], "second")
        self.assertEqual(len(d["latest"]["sha256"]), 64)
        self.assertEqual(d["latest"]["download_url"], "/api/v1/app/android/2/download/")
        self.assertNotIn("apk", d["latest"])
        self.assertNotIn("download_count", d["latest"])

    def test_download_is_byte_identical_and_labelled(self):
        rel = self.register(version="1.0.0", code=1, publish=True)
        r = self.client.get("/api/v1/app/android/1/download/")
        self.assertEqual(r.status_code, 200)
        body = b"".join(r.streaming_content)
        self.assertEqual(hashlib.sha256(body).hexdigest(), rel.sha256)
        self.assertEqual(r["Content-Type"], "application/vnd.android.package-archive")
        self.assertEqual(r["X-Content-SHA256"], rel.sha256)
        self.assertEqual(r["Content-Length"], str(rel.size_bytes))
        self.assertIn('filename="mebelchi-ai-1.0.0.apk"', r["Content-Disposition"])
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        latest = self.client.get("/api/v1/app/android/latest/download/")
        self.assertEqual(b"".join(latest.streaming_content), body)

    def test_download_counts_and_needs_no_login(self):
        self.register(code=1, publish=True)
        for _ in range(2):
            b"".join(self.client.get("/api/v1/app/android/1/download/").streaming_content)
        self.assertEqual(AppRelease.objects.get().download_count, 2)

    def test_unpublished_development_unknown_and_missing_files_answer_404(self):
        self.register(code=1)
        dev = self.register(code=2, channel="development")
        self.assertEqual(self.client.get("/api/v1/app/android/1/download/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/app/android/{dev.version_code}/download/").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/app/android/99/download/").status_code, 404)
        pub = self.register(version="1.2.0", code=3, publish=True)
        Path(pub.apk.path).unlink()
        self.assertEqual(self.client.get("/api/v1/app/android/3/download/").status_code, 404)

    def test_no_path_traversal_through_the_code(self):
        self.assertEqual(self.client.get("/api/v1/app/android/..%2F..%2Fetc%2Fpasswd/download/").status_code, 404)


class AccelRedirectTests(ReleaseBase):
    def test_behind_nginx_the_file_is_handed_over_not_streamed(self):
        rel = self.register(code=1, publish=True)
        with override_settings(RELEASES_X_ACCEL_PREFIX="/_protected/releases/"):
            r = self.client.get("/api/v1/app/android/1/download/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["X-Accel-Redirect"], "/_protected/releases/" + Path(rel.apk.name).name)
        self.assertEqual(r.content, b"")
        self.assertEqual(r["X-Content-SHA256"], rel.sha256)
        self.assertIn("mebelchi-ai-1.0.0.apk", r["Content-Disposition"])
        self.assertEqual(AppRelease.objects.get().download_count, 1)

    def test_unpublished_builds_are_never_handed_over(self):
        self.register(code=1)
        with override_settings(RELEASES_X_ACCEL_PREFIX="/_protected/releases/"):
            r = self.client.get("/api/v1/app/android/1/download/")
        self.assertEqual(r.status_code, 404)
        self.assertNotIn("X-Accel-Redirect", r)

    def test_missing_file_is_404_not_a_broken_redirect(self):
        rel = self.register(code=1, publish=True)
        Path(rel.apk.path).unlink()
        with override_settings(RELEASES_X_ACCEL_PREFIX="/_protected/releases/"):
            self.assertEqual(self.client.get("/api/v1/app/android/1/download/").status_code, 404)


class ExternalUrlTests(ReleaseBase):
    def test_download_redirects_to_the_external_https_address_and_counts(self):
        rel = self.register(code=1, publish=True, external_url="https://github.com/o/r/releases/download/v1/app.apk")
        r = self.client.get("/api/v1/app/android/1/download/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "https://github.com/o/r/releases/download/v1/app.apk")
        self.assertEqual(r["X-Content-SHA256"], rel.sha256)
        rel.refresh_from_db()
        self.assertEqual(rel.download_count, 1)

    def test_latest_alias_also_redirects(self):
        self.register(code=1, publish=True, external_url="https://example.com/a.apk")
        self.assertEqual(self.client.get("/api/v1/app/android/1/download/").status_code, 302)

    def test_only_https_is_accepted(self):
        with self.assertRaises(services.ReleaseError):
            self.register(code=1, external_url="http://example.com/a.apk")
        self.assertFalse(AppRelease.objects.exists())

    def test_an_unpublished_external_release_is_not_reachable(self):
        self.register(code=1, publish=False, external_url="https://example.com/a.apk")
        self.assertEqual(self.client.get("/api/v1/app/android/1/download/").status_code, 404)

    def test_command_takes_external_url(self):
        call_command("publish_android_release", apk=str(self.apk()), app_version="1.0.0", code=1, notes="", channel="production", publish=True, notes_file="", external_url="https://example.com/a.apk")
        self.assertEqual(AppRelease.objects.get().external_url, "https://example.com/a.apk")


class CommandTests(ReleaseBase):
    def test_command_registers_and_publishes(self):
        out = io.StringIO()
        call_command("publish_android_release", apk=str(self.apk()), app_version="1.0.0", code=1, notes="n", channel="production", publish=True, notes_file="", stdout=out)
        rel = AppRelease.objects.get()
        self.assertTrue(rel.is_published)
        self.assertIn(rel.sha256, out.getvalue())

    def test_command_reports_errors_clearly(self):
        bad = Path(self._src.name) / "bad.apk"
        bad.write_bytes(b"x")
        with self.assertRaises(CommandError):
            call_command("publish_android_release", apk=str(bad), app_version="1.0.0", code=1, notes="", channel="production", publish=False, notes_file="")
