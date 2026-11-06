"""USGS feed client — stdlib only (urllib), no API key needed.

Feeds: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/
    <band>_<period>.geojson
Periods: hour, day, week, month. Bands: all, 4.5, 2.5, 1.0, significant.
Feeds update every minute. Never invents data: a failed fetch raises
FetchError and the CLI exits 2.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from .model import Quake, parse_geojson

BASE_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary"

PERIODS = ("hour", "day", "week", "month")
BANDS = ("all", "4.5", "2.5", "1.0", "significant")

DEFAULT_TIMEOUT = 15


class FetchError(Exception):
    """Raised when a USGS feed (or a local snapshot file) cannot be read."""


def feed_url(period: str = "day", band: str = "all") -> str:
    """Canonical USGS feed URL for a period/band pair."""
    if period not in PERIODS:
        raise ValueError(f"unknown period {period!r}; choose from {PERIODS}")
    if band not in BANDS:
        raise ValueError(f"unknown band {band!r}; choose from {BANDS}")
    return f"{BASE_URL}/{band}_{period}.geojson"


def fetch_feed(period: str = "day", band: str = "all", timeout: int = DEFAULT_TIMEOUT) -> list[Quake]:
    """Fetch a live USGS feed and parse it. Raises FetchError on any failure."""
    url = feed_url(period, band)
    request = urllib.request.Request(url, headers={"User-Agent": "QuakeWatch/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise FetchError(f"could not reach USGS feed {url}: {exc}") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise FetchError(f"USGS feed {url} returned invalid JSON: {exc}") from exc
    return parse_geojson(data)


def load_file(path: str | Path) -> list[Quake]:
    """Load quakes from a saved USGS GeoJSON snapshot file."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FetchError(f"snapshot file not found: {path}") from exc
    except (ValueError, OSError) as exc:
        raise FetchError(f"could not read snapshot file {path}: {exc}") from exc
    if not isinstance(data, dict) or "features" not in data:
        raise FetchError(f"not a USGS GeoJSON FeatureCollection: {path}")
    return parse_geojson(data)
