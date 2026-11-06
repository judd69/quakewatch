# QuakeWatch

**The ground never sleeps. Now you can watch it.**

QuakeWatch is a live earthquake monitor built on the U.S. Geological Survey's
real-time feeds — free, keyless, updated every minute. It shows every quake on
Earth, from magnitude 0.3 tremors in Alaska to magnitude 6+ events in the Fiji
region, as a CLI, a JSON API, a self-contained HTML report, and a live web
dashboard with a world map.

- **Live demo:** https://judd69.github.io/quakewatch/
- **Repository:** https://github.com/judd69/quakewatch

## The problem

Earthquakes happen constantly — hundreds a day — but the data lives in feeds
and tables that nobody watches. If you felt a tremor, or you just want to know
what the planet did in the last 24 hours, you have to dig through the USGS site
yourself. QuakeWatch turns that feed into something you can glance at: a map,
a table, and a one-line summary, always current.

## What it does

- **Live CLI** — fetch the current USGS feed and print a coloured summary + table
- **Filters** — minimum magnitude, place substring, radius around a point
  (`--near LAT LON --radius KM`), time window
- **Stats** — total, counts by magnitude band (<3, 3–4.5, 4.5–6, 6+), largest
  quake, most active region, felt reports, tsunami-flagged count, newest quake
- **Outputs** — coloured text, `--format json`, or a self-contained interactive
  HTML report (sortable table, magnitude band chips, stats cards, zero external assets)
- **Live dashboard** — `--serve [PORT]`: stdlib-only web server with a dashboard
  page and a `/api/quakes?period=&min_mag=` JSON endpoint (60s cache, honest
  error JSON when USGS is unreachable)
- **Watch mode** — `--watch SECONDS` polls the feed and prints only newly-seen quakes
- **Offline mode** — `--from-file` loads a saved USGS GeoJSON snapshot instead
  of fetching live (the two snapshots in `examples/` are the offline proof data)

## Requirements

Python 3.9+ — **standard library only, zero dependencies to install.**

## How to run it

```bash
# Last 24 hours, all magnitudes
python3 -m quakewatch

# Last week, magnitude 4.5 and up
python3 -m quakewatch --period week --min-mag 4.5

# Quakes within 500 km of the Fiji region
python3 -m quakewatch --near -21.2 -178.7 --radius 500

# Everything in Alaska
python3 -m quakewatch --place Alaska

# JSON output
python3 -m quakewatch --format json > quakes.json

# Self-contained HTML report
python3 -m quakewatch --format html > report.html

# Live dashboard on http://127.0.0.1:8000/
python3 -m quakewatch --serve 8000

# Watch for new quakes, checking every 60 seconds
python3 -m quakewatch --watch 60

# Offline: use a saved snapshot
python3 -m quakewatch --from-file examples/all_day-2026-11-06.geojson --min-mag 4.5
```

## Example output

Real output from the saved snapshot `examples/all_day-2026-11-06.geojson`
(228 quakes, captured 2026-11-06), run as
`python3 -m quakewatch --from-file examples/all_day-2026-11-06.geojson --min-mag 4.5`
(colour codes stripped for display):

```
QuakeWatch — earthquakes, last snapshot
Total: 10 quakes
By magnitude: <3: 0, 3–4.5: 0, 4.5–6: 9, 6+: 1
Largest: M6.1 — Fiji region (2026-11-05T17:21:45.305000+00:00)
Most active region: Isangel, Vanuatu (1 quake)
Felt reports: 2 quakes felt (161 reports)  ·  Tsunami-flagged: 0

MAG   TIME (UTC)            PLACE                                                  DEPTH  FELT
M4.6  2026-11-06 01:37      58 km WNW of Isangel, Vanuatu                            83km     -
M4.6  2026-11-06 00:02      96 km NNW of Lae, Papua New Guinea                       98km     -
M4.6  2026-11-05 23:04      147 km SSE of False Pass, Alaska                         16km     -
M4.6  2026-11-05 22:34      south of the Fiji Islands                               523km     -
M4.6  2026-11-05 18:05      36 km E of Watari, Japan                                 87km     -
M6.1  2026-11-05 17:21      Fiji region                                             535km     0
M5.0  2026-11-05 16:56      130 km NE of Thang, India                                77km     -
M4.8  2026-11-05 10:09      Sea of Okhotsk                                          554km     -
M5.1  2026-11-05 09:22      19 km NNW of Masumbwe, Tanzania                          10km    19
M5.0  2026-11-05 04:56      111 km W of Petrolia, CA                                 10km   142
```

The full day's snapshot: **228 quakes**, max **M6.1 Fiji region**, **10 at M4.5+**,
**28 at M2.5+**, **9 quakes with felt reports (168 reports total)**, **0 tsunami-flagged**.
Most active region: **Milford, Utah (28 quakes)**.

## Exit codes

| Code | Meaning |
| ---- | ------- |
| 0 | OK — quakes found and printed |
| 1 | No quakes matched the filters (not an error, just empty) |
| 2 | Fetch / file error — USGS unreachable, bad snapshot, or bad arguments |

A failed live fetch never produces invented data: the CLI exits 2, the dashboard
returns honest error JSON / an error page, and the demo page shows a
"could not reach USGS" state.

## Project layout

```
quakewatch/        Python package (stdlib only)
  client.py        USGS feed fetching (urllib) + snapshot loading
  model.py         Quake dataclass + GeoJSON parsing
  geo.py           haversine distance + radius filtering
  analyze.py       filters + statistics
  report.py        coloured text, JSON, self-contained HTML report
  serve.py         live dashboard server (--serve)
  cli.py           argparse CLI (--watch, --serve, --from-file, ...)
tests/             47 unittest tests (real snapshot data)
docs/index.html    live demo — self-contained page, calls USGS directly from
                   the browser; canvas world map with inlined Natural Earth
                   land outlines, no external assets
examples/          verbatim USGS snapshots from 2026-11-06 (offline proof data)
```

## Tests

```bash
python3 -m unittest discover -s tests -v
# 47 tests, all passing — parsing incl. null magnitudes, haversine against
# known city pairs, every filter family, stats against the real snapshot
# numbers, HTML escaping + self-containment, JSON shape, CLI exit codes.
```

## Data & attribution

Earthquake data: **U.S. Geological Survey (USGS)**,
https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/ — **public domain**.
Land outlines on the demo map: **Natural Earth** (public domain), simplified
from world-atlas `land-110m` TopoJSON and inlined at build time — no map tiles
or libraries load at runtime.

## License

MIT — see [LICENSE](LICENSE).
