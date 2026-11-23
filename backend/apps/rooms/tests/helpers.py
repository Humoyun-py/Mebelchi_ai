import io

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

SIZE = {"width": 4000, "length": 3000, "height": 2700}
DOOR = {"type": "door", "wall": "north", "offset": 1000, "width": 900, "height": 2100, "sill": 0}
WINDOW = {"type": "window", "wall": "east", "offset": 800, "width": 1200, "height": 1200, "sill": 900}
ELEMENTS = {"doors": 1, "windows": 1, "furniture": ["bedside", "wardrobe-2door"]}


def png(name="room.png", size=(40, 30)) -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGB", size, "#c9a27a").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def err_code(response) -> str:
    return response.data["error"]["fields"].get("code", "")
