"""Validation of the colour options shared by the geometry endpoints and saved designs."""
import re

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
# colour groups the editor can paint independently
GROUPS = ("carcass", "fronts", "back", "handle")


def is_hex(v) -> bool:
    return isinstance(v, str) and bool(HEX.match(v))


def clean_colors(colors) -> dict[str, str]:
    """{"carcass": "#c9a27a", "fronts": ...}. Raises ValueError with a readable message on anything else."""
    if colors in (None, {}):
        return {}
    if not isinstance(colors, dict):
        raise ValueError("colors must be an object such as {\"fronts\": \"#b98f63\"}")
    out = {}
    for k, v in colors.items():
        if k not in GROUPS:
            raise ValueError(f"unknown colour group '{k}' (use {', '.join(GROUPS)})")
        if not is_hex(v):
            raise ValueError(f"{k} must be a hex colour like #c9a27a")
        out[k] = v.lower()
    return out
