"""Registering a built APK as a release. Everything the public page shows (size, checksum) is computed here from the file itself."""
import hashlib
import re
import zipfile
from pathlib import Path

from django.core.files import File
from django.db import transaction
from django.utils import timezone

from .models import VERSION_RE, AppRelease

MAX_APK_BYTES = 200 * 1024 * 1024


class ReleaseError(ValueError):
    pass


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_apk(path: Path) -> None:
    """Cheap sanity check, not a signature check (the build script verifies the signature with apksigner): it must be a zip that
    contains an Android manifest and compiled code."""
    if not path.is_file():
        raise ReleaseError(f"{path} is not a file")
    size = path.stat().st_size
    if size == 0 or size > MAX_APK_BYTES:
        raise ReleaseError(f"The file must be between 1 byte and {MAX_APK_BYTES // (1024 * 1024)} MB")
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
    except zipfile.BadZipFile as exc:
        raise ReleaseError("The file is not a valid APK (not a zip archive)") from exc
    if "AndroidManifest.xml" not in names or not any(n.endswith(".dex") for n in names):
        raise ReleaseError("The file is not an Android app (no AndroidManifest.xml or classes.dex)")


@transaction.atomic
def register_apk(path: str | Path, *, version_name: str, version_code: int, notes: str = "",
                 channel: str = AppRelease.Channel.PRODUCTION, publish: bool = False, external_url: str = "") -> AppRelease:
    path = Path(path)
    if external_url and not external_url.startswith("https://"):
        raise ReleaseError("external_url must start with https://")
    if not re.match(VERSION_RE, version_name or ""):
        raise ReleaseError("version_name must look like 1.2.3")
    if isinstance(version_code, bool) or not isinstance(version_code, int) or version_code <= 0:
        raise ReleaseError("version_code must be a positive whole number")
    if channel not in AppRelease.Channel.values:
        raise ReleaseError(f"channel must be one of {', '.join(AppRelease.Channel.values)}")
    check_apk(path)
    if AppRelease.objects.filter(platform="android", channel=channel, version_code=version_code).exists():
        raise ReleaseError(f"Android {channel} version code {version_code} already exists; every build needs a higher number")
    digest = sha256_of(path)
    rel = AppRelease(platform="android", channel=channel, version_name=version_name, version_code=version_code, notes=notes.strip(),
                     sha256=digest, size_bytes=path.stat().st_size, external_url=external_url)
    name = f"mebelchi-ai-{channel}-{version_name}-{version_code}.apk"
    with open(path, "rb") as f:
        rel.apk.save(name, File(f), save=False)
    # the stored copy must be byte-identical to what was checksummed
    stored = Path(rel.apk.path)
    if sha256_of(stored) != digest:
        stored.unlink(missing_ok=True)
        raise ReleaseError("The stored copy does not match the checksum; nothing was saved")
    rel.save()
    if publish:
        publish_release(rel)
    return rel


def publish_release(rel: AppRelease) -> AppRelease:
    """Android refuses to update to a lower version code, so a production release must be newer than every published one."""
    if rel.channel != AppRelease.Channel.PRODUCTION:
        raise ReleaseError("Only production releases can be published")
    newest = (AppRelease.objects.filter(platform=rel.platform, channel=rel.channel, is_published=True).exclude(pk=rel.pk)
              .order_by("-version_code").first())
    if newest and newest.version_code > rel.version_code:
        raise ReleaseError(f"Version {newest.version_name} ({newest.version_code}) is already published with a higher code")
    rel.is_published = True
    rel.published_at = rel.published_at or timezone.now()
    rel.save(update_fields=["is_published", "published_at"])
    return rel


def unpublish_release(rel: AppRelease) -> AppRelease:
    rel.is_published = False
    rel.save(update_fields=["is_published"])
    return rel


def public_releases():
    return AppRelease.objects.filter(platform="android", channel=AppRelease.Channel.PRODUCTION, is_published=True)

