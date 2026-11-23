"""Validate a file before it is forwarded to the backend. The backend validates again; this keeps bad input off the wire."""
import os
from dataclasses import dataclass

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".dwg", ".dxf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class UploadRejected(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class CheckedUpload:
    filename: str
    content: bytes


def _magic_ok(ext: str, head: bytes) -> bool:
    if ext == ".pdf":
        return head.startswith(b"%PDF-")
    if ext in (".jpg", ".jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == ".webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    # DWG/DXF are text or proprietary binaries; only the extension and size can be checked here.
    return True


def check_upload(filename: str, content: bytes, max_bytes: int) -> CheckedUpload:
    name = os.path.basename(filename or "").strip()
    if not name:
        raise UploadRejected("no_name")
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadRejected("unsupported_type")
    if not content:
        raise UploadRejected("empty")
    if len(content) > max_bytes:
        raise UploadRejected("too_large")
    if not _magic_ok(ext, content[:16]):
        raise UploadRejected("content_mismatch")
    return CheckedUpload(filename=name[:200], content=content)
