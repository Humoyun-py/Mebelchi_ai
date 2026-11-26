from math import asin, cos, radians, sin, sqrt

EARTH_KM = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in km between two points (straight line, not a road distance; the UI says "approx.")."""
    p1, p2 = radians(float(lat1)), radians(float(lat2))
    dphi, dl = p2 - p1, radians(float(lon2) - float(lon1))
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * EARTH_KM * asin(sqrt(a))
