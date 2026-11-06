"""Geography helpers: haversine distance and radius filtering."""

from __future__ import annotations

import math
from typing import Iterable, Sequence

from .model import Quake

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in kilometres."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def distance_to(quakes: Iterable[Quake], lat: float, lon: float) -> list[tuple[Quake, float]]:
    """(quake, distance_km) pairs for every quake, sorted nearest first."""
    pairs = [(q, haversine_km(lat, lon, q.lat, q.lon)) for q in quakes]
    pairs.sort(key=lambda pair: pair[1])
    return pairs


def near(quakes: Sequence[Quake], lat: float, lon: float, radius_km: float) -> list[Quake]:
    """Quakes within ``radius_km`` of (lat, lon), nearest first."""
    return [q for q, _ in distance_to(quakes, lat, lon) if _ <= radius_km]
