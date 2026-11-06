"""Filtering and statistics over a list of Quakes."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from .geo import haversine_km
from .model import Quake

BAND_ORDER = ["<3", "3–4.5", "4.5–6", "6+", "unknown"]


def filter_quakes(
    quakes: Sequence[Quake],
    min_mag: Optional[float] = None,
    place: Optional[str] = None,
    near_lat: Optional[float] = None,
    near_lon: Optional[float] = None,
    radius_km: Optional[float] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[Quake]:
    """Apply all given filters (AND). Quakes with null mag never pass min_mag."""
    out = []
    needle = place.lower() if place else None
    for q in quakes:
        if min_mag is not None and (q.mag is None or q.mag < min_mag):
            continue
        if needle is not None and needle not in q.place.lower():
            continue
        if near_lat is not None and near_lon is not None and radius_km is not None:
            if haversine_km(near_lat, near_lon, q.lat, q.lon) > radius_km:
                continue
        if since is not None and q.time < since:
            continue
        if until is not None and q.time > until:
            continue
        out.append(q)
    return out


def filter_by_time_window(
    quakes: Sequence[Quake], hours: float, now: Optional[datetime] = None
) -> list[Quake]:
    """Quakes from the last ``hours`` hours (relative to ``now``, default UTC now)."""
    now = now or datetime.now(timezone.utc)
    return filter_quakes(quakes, since=now - timedelta(hours=hours))


def compute_stats(quakes: Sequence[Quake]) -> dict:
    """Summary stats. Empty input yields zeroed stats with None largest/newest."""
    bands = Counter(q.band for q in quakes)
    with_mag = [q for q in quakes if q.mag is not None]
    largest = max(with_mag, key=lambda q: q.mag) if with_mag else None
    newest = max(quakes, key=lambda q: q.time) if quakes else None
    regions = Counter(q.region for q in quakes)
    most_active = regions.most_common(1)[0] if regions else (None, 0)
    felt_quakes = [q for q in quakes if q.felt]  # felt > 0: real reports (felt=0 means none)
    return {
        "total": len(quakes),
        "bands": {band: bands.get(band, 0) for band in BAND_ORDER},
        "largest": largest.to_dict() if largest else None,
        "newest": newest.to_dict() if newest else None,
        "most_active_region": most_active[0],
        "most_active_region_count": most_active[1],
        "felt_count": len(felt_quakes),  # quakes with at least one felt report
        "felt_reports_total": sum(q.felt or 0 for q in felt_quakes),
        "tsunami_count": sum(1 for q in quakes if q.tsunami),
        "reviewed_count": sum(1 for q in quakes if q.status == "reviewed"),
        "automatic_count": sum(1 for q in quakes if q.status == "automatic"),
    }
