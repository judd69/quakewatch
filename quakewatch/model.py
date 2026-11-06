"""Data model: one earthquake, parsed from a USGS GeoJSON feature.

USGS GeoJSON feature shape (per feature):
    {"type": "Feature",
     "properties": {"mag": 6.1, "place": "Fiji region", "time": 1793899305305,
                    "url": "...", "felt": 0, "tsunami": 0, "alert": "green",
                    "status": "reviewed", "sig": 572, "magType": "mww", ...},
     "geometry": {"type": "Point", "coordinates": [-178.7145, -21.1984, 535]},
     "id": "us7000tw8r"}

``time`` is epoch milliseconds (UTC). ``mag`` may be null in the feed.
``felt`` is the number of "Did You Feel It?" reports, or null when none.
``tsunami`` is 1 when a tsunami warning was issued, else 0.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class Quake:
    """A single earthquake event."""

    id: str
    mag: Optional[float]
    place: str
    time: datetime  # timezone-aware, UTC
    lat: float
    lon: float
    depth: float  # km
    url: str
    felt: Optional[int]
    tsunami: int  # 0 or 1
    alert: Optional[str]  # green / yellow / orange / red / None
    sig: int
    status: str  # automatic / reviewed
    mag_type: Optional[str]

    @classmethod
    def from_feature(cls, feature: dict) -> "Quake":
        """Build a Quake from one USGS GeoJSON feature dict."""
        props: dict = feature.get("properties") or {}
        geom: dict = feature.get("geometry") or {}
        coords = geom.get("coordinates") or [0.0, 0.0, 0.0]
        lon = float(coords[0]) if len(coords) > 0 else 0.0
        lat = float(coords[1]) if len(coords) > 1 else 0.0
        depth = float(coords[2]) if len(coords) > 2 else 0.0
        mag = props.get("mag")
        felt = props.get("felt")
        return cls(
            id=str(feature.get("id") or props.get("code") or ""),
            mag=float(mag) if mag is not None else None,
            place=str(props.get("place") or "Unknown location"),
            time=datetime.fromtimestamp(
                float(props.get("time") or 0) / 1000.0, tz=timezone.utc
            ),
            lat=lat,
            lon=lon,
            depth=depth,
            url=str(props.get("url") or ""),
            felt=int(felt) if felt is not None else None,
            tsunami=int(props.get("tsunami") or 0),
            alert=props.get("alert"),
            sig=int(props.get("sig") or 0),
            status=str(props.get("status") or "unknown"),
            mag_type=props.get("magType"),
        )

    @property
    def region(self) -> str:
        """Most active region grouping: the place string after 'of '.

        e.g. '63 km SE of Pope-Vannoy Landing, Alaska' -> 'Pope-Vannoy Landing, Alaska'
        Places with no 'of ' (e.g. 'Fiji region') are used as-is.
        """
        if " of " in self.place:
            return self.place.split(" of ", 1)[1]
        return self.place

    @property
    def band(self) -> str:
        """Magnitude band label used for colouring and stats."""
        if self.mag is None:
            return "unknown"
        if self.mag < 3:
            return "<3"
        if self.mag < 4.5:
            return "3–4.5"
        if self.mag < 6:
            return "4.5–6"
        return "6+"

    def to_dict(self) -> dict:
        """JSON-serialisable representation."""
        return {
            "id": self.id,
            "mag": self.mag,
            "place": self.place,
            "region": self.region,
            "time": self.time.isoformat(),
            "lat": self.lat,
            "lon": self.lon,
            "depth_km": self.depth,
            "url": self.url,
            "felt": self.felt,
            "tsunami": self.tsunami,
            "alert": self.alert,
            "sig": self.sig,
            "status": self.status,
            "mag_type": self.mag_type,
            "band": self.band,
        }


def parse_geojson(data: dict) -> list[Quake]:
    """Parse a USGS GeoJSON FeatureCollection dict into Quakes."""
    features = data.get("features") or []
    return [Quake.from_feature(f) for f in features if isinstance(f, dict)]


def epoch_ms_to_datetime(ms: float) -> datetime:
    """Epoch milliseconds -> timezone-aware UTC datetime."""
    return datetime.fromtimestamp(float(ms) / 1000.0, tz=timezone.utc)
