import os

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
FILE_EXT = {".pdf", ".dwg", ".dxf", ".xlsx", ".csv", ".txt", ".glb", ".gltf", ".obj", ".jpg", ".jpeg", ".png", ".webp"}


def validate_image(f):
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in IMAGE_EXT:
        raise ValidationError("Unsupported image type. Allowed: JPG, PNG, WEBP.")
    if f.size > settings.MAX_IMAGE_UPLOAD_BYTES:
        raise ValidationError("Image too large (max 10 MB).")
    try:
        f.seek(0)
        img = Image.open(f)
        img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValidationError("File is not a valid image.")
    finally:
        f.seek(0)


def validate_document(f):
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in FILE_EXT:
        raise ValidationError(f"Unsupported file type. Allowed: {', '.join(sorted(FILE_EXT))}.")
    if f.size > settings.MAX_FILE_UPLOAD_BYTES:
        raise ValidationError("File too large (max 25 MB).")
    if ext == ".pdf":
        f.seek(0)
        head = f.read(5)
        f.seek(0)
        if head != b"%PDF-":
            raise ValidationError("File is not a valid PDF.")
