from __future__ import annotations

import math
from collections.abc import Iterable

EARTH_RADIUS_M = 6_371_008.8


def valid_fix(lat: float, lon: float) -> bool:
    """True for a plausible coordinate pair; rejects NaN/inf, out-of-range and the 0,0 placeholder."""
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return False
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return False
    return not (lat == 0.0 and lon == 0.0)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def centroid(points: Iterable[tuple[float, float]]) -> tuple[float, float] | None:
    """Mean position via unit vectors, so clusters straddling the antimeridian stay correct."""
    x = y = z = 0.0
    n = 0
    for lat, lon in points:
        phi, lmb = math.radians(lat), math.radians(lon)
        x += math.cos(phi) * math.cos(lmb)
        y += math.cos(phi) * math.sin(lmb)
        z += math.sin(phi)
        n += 1
    if n == 0:
        return None
    x, y, z = x / n, y / n, z / n
    hyp = math.hypot(x, y)
    if hyp == 0.0 and z == 0.0:
        return None
    return math.degrees(math.atan2(z, hyp)), math.degrees(math.atan2(y, x))


def radius_m(center: tuple[float, float], points: Iterable[tuple[float, float]]) -> float:
    """Largest distance from ``center`` to any point, in metres."""
    return max((haversine_m(center[0], center[1], lat, lon) for lat, lon in points), default=0.0)
