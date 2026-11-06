"""Tests for QuakeWatch. Run: python3 -m unittest discover -s tests -v"""

import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quakewatch.analyze import compute_stats, filter_by_time_window, filter_quakes
from quakewatch.client import BANDS, PERIODS, feed_url, load_file
from quakewatch.cli import main as cli_main
from quakewatch.geo import distance_to, haversine_km, near
from quakewatch.model import Quake, epoch_ms_to_datetime, parse_geojson
from quakewatch.report import render_html, render_json, render_text

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "examples" / "all_day-2026-11-06.geojson"
SNAPSHOT_45 = ROOT / "examples" / "4.5_day-2026-11-06.geojson"


def load_snapshot():
    return parse_geojson(json.loads(SNAPSHOT.read_text()))


def make_quake(**overrides):
    base = {
        "id": "test1",
        "mag": 5.2,
        "place": "100 km W of Testville, Alaska",
        "time": datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc),
        "lat": 61.0,
        "lon": -150.0,
        "depth": 10.0,
        "url": "https://earthquake.usgs.gov/earthquakes/eventpage/test1",
        "felt": 3,
        "tsunami": 0,
        "alert": "green",
        "sig": 400,
        "status": "reviewed",
        "mag_type": "mw",
    }
    base.update(overrides)
    return Quake(**base)


class TestModel(unittest.TestCase):
    def test_parse_snapshot_count(self):
        self.assertEqual(len(load_snapshot()), 228)

    def test_parse_null_mag(self):
        feature = {
            "id": "nullmag",
            "properties": {"mag": None, "place": "Nowhere", "time": 1793930000000,
                           "url": "", "felt": None, "tsunami": 0, "alert": None,
                           "status": "automatic", "sig": 0, "magType": None},
            "geometry": {"type": "Point", "coordinates": [10.0, 20.0, 5.0]},
        }
        q = Quake.from_feature(feature)
        self.assertIsNone(q.mag)
        self.assertEqual(q.band, "unknown")
        self.assertEqual((q.lat, q.lon, q.depth), (20.0, 10.0, 5.0))

    def test_epoch_ms_to_datetime(self):
        dt = epoch_ms_to_datetime(1793899305305)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_largest_snapshot_quake(self):
        quakes = load_snapshot()
        largest = max((q for q in quakes if q.mag is not None), key=lambda q: q.mag)
        self.assertEqual(largest.mag, 6.1)
        self.assertEqual(largest.place, "Fiji region")
        self.assertAlmostEqual(largest.lat, -21.1984, places=3)
        self.assertAlmostEqual(largest.lon, -178.7145, places=3)
        self.assertEqual(largest.mag_type, "mww")

    def test_region_after_of(self):
        q = make_quake(place="63 km SE of Pope-Vannoy Landing, Alaska")
        self.assertEqual(q.region, "Pope-Vannoy Landing, Alaska")

    def test_region_no_of(self):
        q = make_quake(place="Fiji region")
        self.assertEqual(q.region, "Fiji region")

    def test_to_dict_round_trip(self):
        q = make_quake()
        d = q.to_dict()
        self.assertEqual(d["id"], "test1")
        self.assertEqual(d["mag"], 5.2)
        self.assertEqual(d["band"], "4.5–6")
        self.assertIn("2026-11-06", d["time"])

    def test_bands(self):
        self.assertEqual(make_quake(mag=1.5).band, "<3")
        self.assertEqual(make_quake(mag=3.0).band, "3–4.5")
        self.assertEqual(make_quake(mag=4.5).band, "4.5–6")
        self.assertEqual(make_quake(mag=6.0).band, "6+")
        self.assertEqual(make_quake(mag=None).band, "unknown")


class TestGeo(unittest.TestCase):
    def test_haversine_same_point_zero(self):
        self.assertEqual(haversine_km(0, 0, 0, 0), 0.0)

    def test_haversine_london_paris(self):
        # London (51.5074, -0.1278) to Paris (48.8566, 2.3522) ≈ 343 km
        d = haversine_km(51.5074, -0.1278, 48.8566, 2.3522)
        self.assertAlmostEqual(d, 343, delta=5)

    def test_haversine_new_york_los_angeles(self):
        # ≈ 3,944 km
        d = haversine_km(40.7128, -74.0060, 34.0522, -118.2437)
        self.assertAlmostEqual(d, 3944, delta=30)

    def test_haversine_antipodal_sanity(self):
        d = haversine_km(0, 0, 0, 180)
        self.assertAlmostEqual(d, math.pi * 6371.0, delta=1)

    def test_haversine_symmetric(self):
        self.assertAlmostEqual(
            haversine_km(10, 20, 30, 40), haversine_km(30, 40, 10, 20))

    def test_near_fiji_catches_m61(self):
        quakes = load_snapshot()
        found = near(quakes, -21.2, -178.7, 500)
        self.assertTrue(any(q.mag == 6.1 for q in found))
        self.assertTrue(all(
            haversine_km(-21.2, -178.7, q.lat, q.lon) <= 500 for q in found))

    def test_near_tiny_radius_empty(self):
        quakes = load_snapshot()
        self.assertEqual(near(quakes, 0.0, 0.0, 1), [])

    def test_distance_to_sorted(self):
        quakes = [make_quake(id="a", lat=0, lon=0), make_quake(id="b", lat=10, lon=0)]
        pairs = distance_to(quakes, 0, 0)
        self.assertEqual(pairs[0][0].id, "a")
        self.assertEqual(pairs[0][1], 0.0)
        self.assertGreater(pairs[1][1], 1000)


class TestAnalyze(unittest.TestCase):
    def setUp(self):
        self.quakes = load_snapshot()

    def test_stats_snapshot_numbers(self):
        stats = compute_stats(self.quakes)
        self.assertEqual(stats["total"], 228)
        self.assertEqual(stats["largest"]["mag"], 6.1)
        self.assertEqual(stats["largest"]["place"], "Fiji region")
        self.assertEqual(stats["bands"]["6+"], 1)
        self.assertEqual(stats["bands"]["4.5–6"], 9)
        self.assertEqual(stats["bands"]["<3"] + stats["bands"]["3–4.5"]
                         + stats["bands"]["4.5–6"] + stats["bands"]["6+"], 228)
        self.assertEqual(stats["felt_count"], 9)
        self.assertEqual(stats["felt_reports_total"], 168)
        self.assertEqual(stats["tsunami_count"], 0)
        self.assertEqual(stats["most_active_region"], "Milford, Utah")
        self.assertEqual(stats["most_active_region_count"], 28)

    def test_stats_45_snapshot(self):
        quakes = parse_geojson(json.loads(SNAPSHOT_45.read_text()))
        self.assertEqual(len(quakes), 10)
        stats = compute_stats(quakes)
        self.assertEqual(stats["total"], 10)
        self.assertEqual(stats["bands"]["6+"], 1)

    def test_stats_empty(self):
        stats = compute_stats([])
        self.assertEqual(stats["total"], 0)
        self.assertIsNone(stats["largest"])
        self.assertIsNone(stats["newest"])
        self.assertEqual(stats["felt_count"], 0)

    def test_filter_min_mag(self):
        self.assertEqual(len(filter_quakes(self.quakes, min_mag=4.5)), 10)
        self.assertEqual(len(filter_quakes(self.quakes, min_mag=6.0)), 1)
        self.assertEqual(len(filter_quakes(self.quakes, min_mag=9.0)), 0)

    def test_filter_min_mag_excludes_null(self):
        qs = [make_quake(id="n", mag=None), make_quake(id="y", mag=5.0)]
        self.assertEqual([q.id for q in filter_quakes(qs, min_mag=4.0)], ["y"])

    def test_filter_place_case_insensitive(self):
        found = filter_quakes(self.quakes, place="fiji")
        self.assertEqual(len(found), 2)  # "Fiji region" + "south of the Fiji Islands"
        self.assertTrue(all("Fiji" in q.place for q in found))
        alaska = filter_quakes(self.quakes, place="ALASKA")
        self.assertEqual(len(alaska), 84)

    def test_filter_place_no_match(self):
        self.assertEqual(filter_quakes(self.quakes, place="zzz-no-such-place"), [])

    def test_filter_radius(self):
        found = filter_quakes(self.quakes, near_lat=-21.2, near_lon=-178.7, radius_km=500)
        self.assertTrue(any(q.mag == 6.1 for q in found))

    def test_filter_time_window(self):
        now = datetime(2026, 11, 6, 23, 0, tzinfo=timezone.utc)
        recent = filter_by_time_window(self.quakes, hours=1, now=now)
        self.assertTrue(all(q.time >= datetime(2026, 11, 6, 22, 0, tzinfo=timezone.utc)
                            for q in recent))
        self.assertLess(len(recent), 228)

    def test_newest_is_latest_time(self):
        stats = compute_stats(self.quakes)
        newest_time = max(q.time for q in self.quakes)
        self.assertEqual(stats["newest"]["time"], newest_time.isoformat())


class TestReport(unittest.TestCase):
    def setUp(self):
        self.quakes = load_snapshot()
        self.stats = compute_stats(self.quakes)

    def test_text_contains_key_numbers(self):
        text = render_text(self.quakes, self.stats, "day")
        self.assertIn("228", text)
        self.assertIn("6.1", text)
        self.assertIn("Fiji region", text)

    def test_json_shape(self):
        payload = json.loads(render_json(self.quakes, self.stats))
        self.assertEqual(payload["stats"]["total"], 228)
        self.assertEqual(len(payload["quakes"]), 228)
        self.assertEqual(payload["quakes"][0]["mag"], payload["stats"]["newest"]["mag"])
        self.assertIn("band", payload["quakes"][0])
        self.assertIn("url", payload["quakes"][0])

    def test_json_sorted_newest_first(self):
        payload = json.loads(render_json(self.quakes, self.stats))
        times = [q["time"] for q in payload["quakes"]]
        self.assertEqual(times, sorted(times, reverse=True))

    def test_html_escapes_place(self):
        evil = make_quake(place='<script>alert("x")</script> & "quoted"')
        out = render_html([evil], compute_stats([evil]))
        self.assertNotIn('<script>alert("x")</script>', out)
        self.assertIn("&lt;script&gt;", out)
        self.assertIn("&amp;", out)

    def test_html_self_contained(self):
        out = render_html(self.quakes, self.stats)
        self.assertNotIn("src=", out)
        self.assertNotIn("<link", out)
        self.assertNotIn("http://", out.replace("https://earthquake.usgs.gov", ""))
        self.assertIn("Fiji region", out)
        self.assertIn("228", out)
        # every quake row present
        self.assertEqual(out.count("<tr data-mag="), 228)

    def test_html_sortable_headers(self):
        out = render_html(self.quakes, self.stats)
        self.assertIn('data-sort="mag"', out)
        self.assertIn('data-sort="time"', out)


class TestClient(unittest.TestCase):
    def test_feed_url_shapes(self):
        self.assertEqual(
            feed_url("day", "all"),
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson")
        self.assertEqual(
            feed_url("week", "4.5"),
            "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson")

    def test_feed_url_rejects_bad_period(self):
        with self.assertRaises(ValueError):
            feed_url("year", "all")

    def test_periods_and_bands(self):
        self.assertEqual(set(PERIODS), {"hour", "day", "week", "month"})
        self.assertEqual(set(BANDS), {"all", "4.5", "2.5", "1.0", "significant"})

    def test_load_file_snapshot(self):
        self.assertEqual(len(load_file(SNAPSHOT)), 228)

    def test_load_file_missing_raises(self):
        from quakewatch.client import FetchError
        with self.assertRaises(FetchError):
            load_file(ROOT / "examples" / "nope.geojson")

    def test_load_file_invalid_json_raises(self):
        from quakewatch.client import FetchError
        with tempfile.NamedTemporaryFile("w", suffix=".geojson", delete=False) as fh:
            fh.write("{not json")
            name = fh.name
        try:
            with self.assertRaises(FetchError):
                load_file(name)
        finally:
            os.unlink(name)


class TestCLI(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "quakewatch", *args],
            cwd=ROOT, capture_output=True, text=True, timeout=60,
        )

    def test_cli_text_snapshot(self):
        res = self.run_cli("--from-file", str(SNAPSHOT))
        self.assertEqual(res.returncode, 0)
        self.assertIn("228", res.stdout)
        self.assertIn("6.1", res.stdout)
        self.assertIn("Fiji region", res.stdout)

    def test_cli_min_mag(self):
        res = self.run_cli("--from-file", str(SNAPSHOT), "--min-mag", "4.5")
        self.assertEqual(res.returncode, 0)
        self.assertIn("Total: 10 quakes", res.stdout)

    def test_cli_json(self):
        res = self.run_cli("--from-file", str(SNAPSHOT), "--format", "json")
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["stats"]["total"], 228)

    def test_cli_no_match_exit_1(self):
        res = self.run_cli("--from-file", str(SNAPSHOT), "--min-mag", "9.5")
        self.assertEqual(res.returncode, 1)

    def test_cli_missing_file_exit_2(self):
        res = self.run_cli("--from-file", "no-such-file.geojson")
        self.assertEqual(res.returncode, 2)
        self.assertIn("error", res.stderr.lower())

    def test_cli_near_fiji(self):
        res = self.run_cli("--from-file", str(SNAPSHOT),
                           "--near", "-21.2", "-178.7", "--radius", "500")
        self.assertEqual(res.returncode, 0)
        self.assertIn("6.1", res.stdout)
        self.assertIn("Fiji region", res.stdout)

    def test_cli_html(self):
        res = self.run_cli("--from-file", str(SNAPSHOT), "--format", "html")
        self.assertEqual(res.returncode, 0)
        self.assertIn("<!DOCTYPE html>", res.stdout)
        self.assertIn("Fiji region", res.stdout)

    def test_cli_bad_period_exit_2(self):
        res = self.run_cli("--period", "year")
        self.assertEqual(res.returncode, 2)

    def test_cli_direct_call_exit_codes(self):
        self.assertEqual(cli_main(["--from-file", str(SNAPSHOT), "--min-mag", "9.9"]), 1)
        self.assertEqual(cli_main(["--from-file", "nope.geojson"]), 2)


if __name__ == "__main__":
    unittest.main()
