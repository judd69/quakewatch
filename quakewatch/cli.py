"""QuakeWatch CLI.

Exit codes
----------
0  ok (quakes found and printed)
1  no quakes matched the filters — not an error, just empty
2  fetch / file error (USGS unreachable, bad snapshot, bad arguments)

Examples
--------
    python3 -m quakewatch                       # last day, all magnitudes
    python3 -m quakewatch --period week --min-mag 4.5
    python3 -m quakewatch --near -21.2 -178.7 --radius 500
    python3 -m quakewatch --format json > quakes.json
    python3 -m quakewatch --format html > report.html
    python3 -m quakewatch --from-file examples/all_day-2026-11-06.geojson
    python3 -m quakewatch --serve 8000         # live dashboard
    python3 -m quakewatch --watch 60           # print new quakes every minute
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .analyze import compute_stats, filter_quakes
from .client import BANDS, PERIODS, FetchError, fetch_feed, load_file
from .report import render_html, render_json, render_text

EXIT_OK = 0
EXIT_NO_MATCH = 1
EXIT_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quakewatch",
        description="Live earthquake monitor on USGS real-time feeds.",
    )
    parser.add_argument("--period", default="day", choices=PERIODS,
                        help="feed period (default: day)")
    parser.add_argument("--band", default="all", choices=BANDS,
                        help="USGS magnitude band (default: all)")
    parser.add_argument("--min-mag", type=float, default=None,
                        help="only quakes at or above this magnitude")
    parser.add_argument("--near", nargs=2, type=float, metavar=("LAT", "LON"),
                        default=None, help="latitude and longitude to search around")
    parser.add_argument("--radius", type=float, default=None,
                        help="radius in km for --near (required with --near)")
    parser.add_argument("--place", default=None,
                        help="case-insensitive substring match on place name")
    parser.add_argument("--format", dest="fmt", default="text",
                        choices=("text", "json", "html"),
                        help="output format (default: text)")
    parser.add_argument("--from-file", default=None, metavar="FILE",
                        help="load a saved USGS GeoJSON snapshot instead of fetching live")
    parser.add_argument("--serve", nargs="?", const=8000, type=int, metavar="PORT",
                        default=None, help="start the live dashboard server (default port 8000)")
    parser.add_argument("--watch", type=int, default=None, metavar="SECONDS",
                        help="poll the feed every N seconds, printing only newly-seen quakes")
    return parser


def load_quakes(args: argparse.Namespace):
    """Fetch live or load a snapshot; returns (quakes, source_label)."""
    if args.from_file:
        return load_file(args.from_file), f"file {args.from_file}"
    return fetch_feed(period=args.period, band=args.band), f"USGS {args.band}_{args.period}"


def apply_filters(args: argparse.Namespace, quakes):
    near_lat = near_lon = None
    if args.near is not None:
        near_lat, near_lon = args.near
    return filter_quakes(
        quakes,
        min_mag=args.min_mag,
        place=args.place,
        near_lat=near_lat,
        near_lon=near_lon,
        radius_km=args.radius,
    )


def emit(args: argparse.Namespace, quakes, period_label: str) -> int:
    """Render the filtered quakes; 1 when nothing matched."""
    if not quakes:
        print("No quakes match those filters.", file=sys.stderr)
        return EXIT_NO_MATCH
    stats = compute_stats(quakes)
    if args.fmt == "json":
        print(render_json(quakes, stats), end="")
    elif args.fmt == "html":
        print(render_html(quakes, stats, period_label), end="")
    else:
        print(render_text(quakes, stats, period_label), end="")
    return EXIT_OK


def run_watch(args: argparse.Namespace) -> int:
    """Poll the feed every N seconds; print only newly-seen quake ids."""
    seen: set[str] = set()
    try:
        while True:
            try:
                quakes, _ = load_quakes(args)
            except FetchError as exc:
                print(f"fetch failed: {exc}", file=sys.stderr)
                time.sleep(args.watch)
                continue
            filtered = apply_filters(args, quakes)
            new = [q for q in filtered if q.id not in seen]
            for q in sorted(new, key=lambda x: x.time):
                mag = f"M{q.mag:.1f}" if q.mag is not None else "M?"
                print(f"{q.time.strftime('%Y-%m-%d %H:%M UTC')}  {mag}  {q.place}  ({q.id})")
                seen.add(q.id)
            for q in filtered:
                seen.add(q.id)
            sys.stdout.flush()
            time.sleep(args.watch)
    except KeyboardInterrupt:
        print("\nWatch stopped.")
        return EXIT_OK


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.near is not None and args.radius is None:
        parser.error("--radius is required with --near")
    if args.serve is not None:
        from .serve import serve

        serve(args.serve)
        return EXIT_OK
    if args.watch is not None:
        if args.watch <= 0:
            parser.error("--watch needs a positive number of seconds")
        return run_watch(args)
    try:
        quakes, _source = load_quakes(args)
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    filtered = apply_filters(args, quakes)
    period_label = args.period if not args.from_file else "snapshot"
    return emit(args, filtered, period_label)


if __name__ == "__main__":
    raise SystemExit(main())
