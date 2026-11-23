import math


class InvalidNumber(ValueError):
    pass


def parse_number(text: str, minimum: float, maximum: float, integer: bool = False) -> float:
    """Accept '800', '800.5' and '800,5'. Anything else, or out of range, raises InvalidNumber."""
    raw = (text or "").strip().replace(",", ".")
    try:
        value = float(raw)
    except ValueError as exc:
        raise InvalidNumber("not_a_number") from exc
    if not math.isfinite(value):
        raise InvalidNumber("not_a_number")
    if integer and not value.is_integer():
        raise InvalidNumber("not_an_integer")
    if not minimum <= value <= maximum:
        raise InvalidNumber("out_of_range")
    return int(value) if integer else value
