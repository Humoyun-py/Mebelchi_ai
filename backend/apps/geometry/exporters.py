"""Mesh exporters (GLB, glTF, OBJ) written from scratch — no 3D libraries required."""
from __future__ import annotations

import base64
import json
import struct

MM = 0.001  # export in metres

# unit cube faces: (normal, 4 corner offsets) with counter-clockwise winding seen from outside
_FACES = [
    ((1, 0, 0), [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]),
    ((-1, 0, 0), [(0, 0, 1), (0, 1, 1), (0, 1, 0), (0, 0, 0)]),
    ((0, 1, 0), [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)]),
    ((0, -1, 0), [(0, 0, 1), (0, 0, 0), (1, 0, 0), (1, 0, 1)]),
    ((0, 0, 1), [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]),
    ((0, 0, -1), [(1, 0, 0), (0, 0, 0), (0, 1, 0), (1, 1, 0)]),
]


def _box_mesh(b: dict):
    pos, nor, idx = [], [], []
    for n, corners in _FACES:
        base = len(pos)
        for cx, cy, cz in corners:
            pos.append(((b["x"] + cx * b["sx"]) * MM, (b["y"] + cy * b["sy"]) * MM, (b["z"] + cz * b["sz"]) * MM))
            nor.append(n)
        idx += [base, base + 1, base + 2, base, base + 2, base + 3]
    return pos, nor, idx


def _hex_rgba(h: str):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [1.0]


def _gltf_doc(boxes: list[dict]):
    """Returns (json_dict, binary_bytes)."""
    binary = bytearray()
    views, accessors, meshes, nodes, materials, mat_index = [], [], [], [], [], {}
    for i, b in enumerate(boxes):
        pos, nor, idx = _box_mesh(b)
        pb = b"".join(struct.pack("<3f", *p) for p in pos)
        nb = b"".join(struct.pack("<3f", *n) for n in nor)
        ib = b"".join(struct.pack("<H", j) for j in idx)
        ib += b"\x00" * (-len(ib) % 4)
        acc = {}
        for key, data, target in (("p", pb, 34962), ("n", nb, 34962), ("i", ib, 34963)):
            views.append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(data), "target": target})
            acc[key] = len(views) - 1
            binary += data
        xs = [p[0] for p in pos]; ys = [p[1] for p in pos]; zs = [p[2] for p in pos]
        accessors.append({"bufferView": acc["p"], "componentType": 5126, "count": len(pos), "type": "VEC3",
                          "min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]})
        accessors.append({"bufferView": acc["n"], "componentType": 5126, "count": len(nor), "type": "VEC3"})
        accessors.append({"bufferView": acc["i"], "componentType": 5123, "count": len(idx), "type": "SCALAR"})
        color = b.get("color", "#c9a27a")
        if color not in mat_index:
            mat_index[color] = len(materials)
            materials.append({"name": color, "pbrMetallicRoughness": {"baseColorFactor": _hex_rgba(color), "metallicFactor": 0.0, "roughnessFactor": 0.8}})
        base = len(accessors) - 3
        meshes.append({"name": b["name"], "primitives": [{"attributes": {"POSITION": base, "NORMAL": base + 1}, "indices": base + 2,
                                                         "material": mat_index[color]}]})
        nodes.append({"name": b["name"], "mesh": i})
    doc = {"asset": {"version": "2.0", "generator": "MEBELCHI AI"}, "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}],
           "nodes": nodes, "meshes": meshes, "materials": materials, "accessors": accessors, "bufferViews": views,
           "buffers": [{"byteLength": len(binary)}]}
    return doc, bytes(binary)


def to_glb(boxes: list[dict]) -> bytes:
    doc, binary = _gltf_doc(boxes)
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    binary += b"\x00" * (-len(binary) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(binary), 0x004E4942) + binary)


def to_gltf(boxes: list[dict]) -> bytes:
    doc, binary = _gltf_doc(boxes)
    doc["buffers"][0]["uri"] = "data:application/octet-stream;base64," + base64.b64encode(binary).decode()
    return json.dumps(doc).encode()


def to_obj(boxes: list[dict]) -> bytes:
    lines = ["# MEBELCHI AI parametric export (metres)"]
    v_off = 0
    for b in boxes:
        pos, nor, idx = _box_mesh(b)
        lines.append(f"o {b['name'].replace(' ', '_')}")
        lines += [f"v {x:.5f} {y:.5f} {z:.5f}" for x, y, z in pos]
        lines += [f"vn {x} {y} {z}" for x, y, z in nor]
        for k in range(0, len(idx), 3):
            a, c, d = (idx[k] + 1 + v_off, idx[k + 1] + 1 + v_off, idx[k + 2] + 1 + v_off)
            lines.append(f"f {a}//{a} {c}//{c} {d}//{d}")
        v_off += len(pos)
    return ("\n".join(lines) + "\n").encode()
