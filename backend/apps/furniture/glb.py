"""Validation of an uploaded binary glTF (GLB). Only structure is checked: that it is a well-formed glTF 2.0 container with at least one mesh
and no references to external files or URLs. It does NOT check that the dimensions match the catalogue entry; the owner and the platform
administrator review the model before an item is approved."""
import json
import struct

MAGIC, VERSION, JSON_CHUNK = 0x46546C67, 2, 0x4E4F534A
MAX_BYTES = 15 * 1024 * 1024


class GlbError(ValueError):
    pass


def validate_glb(data: bytes) -> dict:
    if len(data) > MAX_BYTES:
        raise GlbError(f"The model is too large (max {MAX_BYTES // 1024 // 1024} MB).")
    if len(data) < 20:
        raise GlbError("This is not a GLB file.")
    magic, version, length = struct.unpack("<III", data[:12])
    if magic != MAGIC:
        raise GlbError("This is not a GLB file (wrong header). Upload a binary .glb; convert .gltf files to .glb first.")
    if version != VERSION:
        raise GlbError("Only glTF 2.0 is supported.")
    if length != len(data):
        raise GlbError("The GLB file is truncated or corrupted (length does not match).")
    chunk_len, chunk_type = struct.unpack("<II", data[12:20])
    if chunk_type != JSON_CHUNK or 20 + chunk_len > len(data):
        raise GlbError("The GLB file is corrupted (bad JSON chunk).")
    try:
        doc = json.loads(data[20:20 + chunk_len].decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise GlbError("The GLB file is corrupted (JSON cannot be read).")
    if not isinstance(doc, dict) or not str((doc.get("asset") or {}).get("version", "")).startswith("2"):
        raise GlbError("Only glTF 2.0 is supported.")
    if not doc.get("meshes"):
        raise GlbError("The model contains no meshes.")
    for kind in ("buffers", "images"):
        for item in doc.get(kind) or []:
            uri = item.get("uri") if isinstance(item, dict) else None
            if uri is not None and not str(uri).startswith("data:"):
                raise GlbError("The model refers to external files or URLs; embed everything in the .glb.")
    return {"meshes": len(doc["meshes"]), "nodes": len(doc.get("nodes") or []), "materials": len(doc.get("materials") or [])}
