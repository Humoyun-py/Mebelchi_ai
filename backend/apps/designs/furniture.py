"""Saved furniture designs: validation of the stored config and rebuilding the model from it.

config (schema_version 1) = {"schema_version": 1, "input": {...engine input...}, "color": "#rrggbb", "colors": {"carcass": ..., "fronts": ...},
"material": <material id or null>}. Older configs have just `input` (7 numbers) and `color`; they stay valid.
"""
from apps.calculations import engine
from apps.geometry import builder, colors as colorlib

SCHEMA_VERSION = 1


def check_config(config: dict) -> None:
    """Raises ValueError with a readable message when a furniture config could not be rebuilt into a real cabinet."""
    if "input" not in config:
        return  # nothing to rebuild (e.g. a design that only keeps notes); allowed for backward compatibility
    inp = config["input"]
    if not isinstance(inp, dict):
        raise ValueError("input must be an object")
    try:
        engine.validate(engine.CabinetInput.from_dict(inp))
    except engine.EngineValidationError as e:
        raise ValueError("input: " + "; ".join(f"{k}: {v}" for k, v in e.errors.items()))
    except TypeError:
        raise ValueError("input needs width, height and depth")
    if "color" in config and config["color"] is not None and not colorlib.is_hex(config["color"]):
        raise ValueError("color must be a hex colour like #c9a27a")
    colorlib.clean_colors(config.get("colors"))
    v = config.get("schema_version", SCHEMA_VERSION)
    if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version (this server understands 1..{SCHEMA_VERSION})")


def rebuild(config: dict) -> dict:
    """Geometry and calculation recomputed from a saved config, so a reopened design always reflects the current, validated numbers."""
    inp = config["input"]
    model = builder.build_cabinet(inp, config.get("color"), colorlib.clean_colors(config.get("colors")), verify=True)
    calc = engine.calculate(inp)
    return {"geometry": model, "calculation": {"summary": calc["summary"], "hardware": calc["hardware"], "warnings": calc["warnings"], "parts": calc["parts"]}}
