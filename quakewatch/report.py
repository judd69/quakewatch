"""Output: coloured text, JSON, and a self-contained interactive HTML report.

The HTML report has zero external assets — inline CSS + JS only, system
font stack — so it renders offline from a saved snapshot.
"""

from __future__ import annotations

import html
import json
from typing import Sequence

from .analyze import compute_stats
from .model import Quake

# --- ANSI colours (text output) -------------------------------------------------
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
AMBER = "\033[38;5;208m"  # seismic amber, matches the web UI accent


def mag_colour(mag) -> str:
    if mag is None:
        return DIM
    if mag >= 6:
        return RED
    if mag >= 4.5:
        return AMBER
    if mag >= 3:
        return YELLOW
    return GREEN


def mag_label(mag) -> str:
    return f"M{mag:.1f}" if mag is not None else "M?"


def render_text(quakes: Sequence[Quake], stats: dict, period: str = "day") -> str:
    """Coloured terminal report."""
    lines = []
    lines.append(f"{BOLD}QuakeWatch — earthquakes, last {period}{RESET}")
    lines.append(f"Total: {stats['total']} quakes")
    bands = stats["bands"]
    lines.append(
        "By magnitude: "
        + ", ".join(f"{b}: {bands[b]}" for b in ["<3", "3–4.5", "4.5–6", "6+"])
    )
    largest = stats["largest"]
    if largest:
        lines.append(
            f"Largest: {mag_colour(largest['mag'])}M{largest['mag']:.1f}{RESET} — "
            f"{largest['place']} ({largest['time']})"
        )
    lines.append(
        f"Most active region: {stats['most_active_region']} "
        f"({stats['most_active_region_count']} "
        f"{'quake' if stats['most_active_region_count'] == 1 else 'quakes'})"
    )
    lines.append(
        f"Felt reports: {stats['felt_count']} quakes felt "
        f"({stats['felt_reports_total']} reports)  ·  "
        f"Tsunami-flagged: {stats['tsunami_count']}"
    )
    lines.append("")
    lines.append(f"{BOLD}{'MAG':<6}{'TIME (UTC)':<22}{'PLACE':<52}{'DEPTH':>8}{'FELT':>6}{RESET}")
    for q in sorted(quakes, key=lambda x: x.time, reverse=True):
        felt = str(q.felt) if q.felt is not None else "-"
        lines.append(
            f"{mag_colour(q.mag)}{mag_label(q.mag):<6}{RESET}"
            f"{q.time.strftime('%Y-%m-%d %H:%M'):<22}"
            f"{q.place[:50]:<52}"
            f"{q.depth:>7.0f}km{felt:>6}"
        )
    return "\n".join(lines) + "\n"


def render_json(quakes: Sequence[Quake], stats: dict) -> str:
    """JSON output: stats + quakes sorted newest first."""
    payload = {
        "stats": stats,
        "quakes": [q.to_dict() for q in sorted(quakes, key=lambda x: x.time, reverse=True)],
    }
    return json.dumps(payload, indent=2) + "\n"


def _esc(text) -> str:
    return html.escape(str(text), quote=True)


# --- HTML report -----------------------------------------------------------------

_HTML_CSS = """
:root{--bg:#0A0A0B;--surface:#1A1A1E;--surface2:#232329;--text:#F5F5F4;
--muted:#A1A1AA;--accent:#F97316;--green:#22C55E;--yellow:#EAB308;--red:#EF4444}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:32px 20px 64px}
h1{font-size:clamp(2rem,5vw,3.2rem);line-height:1.05;margin:.2em 0}
.sub{color:var(--muted);max-width:640px;line-height:1.55}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:28px 0}
.card{background:var(--surface);border:1px solid #2A2A30;border-radius:14px;padding:16px 18px}
.card .k{font-size:.75rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.card .v{font-size:1.9rem;font-weight:800;margin-top:6px}
.card .v.accent{color:var(--accent)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 18px}
.chip{cursor:pointer;border:1px solid #33333A;background:var(--surface);color:var(--text);
border-radius:999px;padding:7px 14px;font-size:.9rem;transition:all .18s cubic-bezier(.34,1.56,.64,1)}
.chip.active{background:var(--accent);border-color:var(--accent);color:#111;font-weight:700}
table{width:100%;border-collapse:collapse;background:var(--surface);border-radius:14px;overflow:hidden}
th,td{padding:10px 12px;text-align:left;font-size:.92rem;border-bottom:1px solid #2A2A30}
th{cursor:pointer;color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.06em}
tr:hover td{background:var(--surface2)}
td.mag{font-weight:800}
a{color:var(--accent)}
footer{color:var(--muted);font-size:.85rem;margin-top:24px;line-height:1.6}
"""

_HTML_JS = """
let sortKey='time', sortDir=-1, bandFilter='all';
const rows=[...document.querySelectorAll('#qtable tbody tr')];
function magBand(m){if(m==null)return 'unknown';if(m<3)return '<3';if(m<4.5)return '3–4.5';if(m<6)return '4.5–6';return '6+';}
function apply(){
  rows.forEach(r=>{
    const m=parseFloat(r.dataset.mag); const show = bandFilter==='all' || magBand(isNaN(m)?null:m)===bandFilter;
    r.style.display = show ? '' : 'none';
  });
}
document.querySelectorAll('.chip').forEach(c=>c.addEventListener('click',()=>{
  document.querySelectorAll('.chip').forEach(x=>x.classList.remove('active'));
  c.classList.add('active'); bandFilter=c.dataset.band; apply();
}));
document.querySelectorAll('#qtable th').forEach(th=>th.addEventListener('click',()=>{
  const key=th.dataset.sort; if(!key) return;
  if(sortKey===key) sortDir*=-1; else {sortKey=key; sortDir=1;}
  const tb=document.querySelector('#qtable tbody');
  const vis=rows.filter(r=>r.style.display!=='none');
  const hid=rows.filter(r=>r.style.display==='none');
  vis.sort((a,b)=>{
    let va=a.dataset[key], vb=b.dataset[key];
    if(key==='mag'||key==='depth'||key==='felt'){va=parseFloat(va)||-1; vb=parseFloat(vb)||-1;}
    return (va<vb?-1:va>vb?1:0)*sortDir;
  });
  vis.forEach(r=>tb.appendChild(r)); hid.forEach(r=>tb.appendChild(r));
}));
"""


def render_html(quakes: Sequence[Quake], stats: dict, period: str = "day") -> str:
    """Single self-contained HTML report: stats cards, band chips, sortable table."""
    ordered = sorted(quakes, key=lambda x: x.time, reverse=True)
    largest = stats["largest"]
    largest_txt = (
        f"M{largest['mag']:.1f} — {_esc(largest['place'])}" if largest else "—"
    )
    rows = []
    for q in ordered:
        rows.append(
            "<tr data-mag='{mag}' data-time='{t}' data-place='{place}' "
            "data-depth='{depth}' data-felt='{felt}'>"
            "<td class='mag'>{maglabel}</td><td>{time}</td><td>{place}</td>"
            "<td>{depth:.0f} km</td><td>{felt}</td>"
            "<td><a href='{url}'>USGS ↗</a></td></tr>".format(
                mag="" if q.mag is None else f"{q.mag:.1f}",
                t=_esc(q.time.isoformat()),
                place=_esc(q.place),
                depth=q.depth,
                felt="" if q.felt is None else q.felt,
                maglabel=_esc(mag_label(q.mag)),
                time=_esc(q.time.strftime("%Y-%m-%d %H:%M UTC")),
                url=_esc(q.url),
            )
        )
    bands = stats["bands"]
    chips = "".join(
        f"<button class='chip{' active' if b == 'all' else ''}' data-band='{_esc(b)}'>"
        f"{_esc(b)} ({bands.get(b, 0) if b != 'all' else stats['total']})</button>"
        for b in ["all", "<3", "3–4.5", "4.5–6", "6+"]
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QuakeWatch — earthquake report ({_esc(period)})</title>
<style>{_HTML_CSS}</style></head>
<body><div class="wrap">
<h1>QuakeWatch</h1>
<p class="sub">Earthquakes over the last {_esc(period)}, from the U.S. Geological Survey
real-time feed. Data: USGS, public domain.</p>
<div class="cards">
<div class="card"><div class="k">Total quakes</div><div class="v">{stats['total']}</div></div>
<div class="card"><div class="k">Largest</div><div class="v accent">{_esc(largest_txt)}</div></div>
<div class="card"><div class="k">M4.5+</div><div class="v">{bands['4.5–6'] + bands['6+']}</div></div>
<div class="card"><div class="k">Felt reports</div><div class="v">{stats['felt_count']} quakes</div></div>
<div class="card"><div class="k">Most active region</div><div class="v" style="font-size:1.15rem">{_esc(stats['most_active_region'] or '—')}</div></div>
<div class="card"><div class="k">Tsunami-flagged</div><div class="v">{stats['tsunami_count']}</div></div>
</div>
<div class="chips">{chips}</div>
<table id="qtable"><thead><tr>
<th data-sort="mag">Mag ↕</th><th data-sort="time">Time (UTC) ↕</th>
<th data-sort="place">Place ↕</th><th data-sort="depth">Depth ↕</th>
<th data-sort="felt">Felt ↕</th><th>Link</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<footer>Source: U.S. Geological Survey (USGS) earthquake feed,
https://earthquake.usgs.gov — public domain data. Generated by QuakeWatch.</footer>
</div><script>{_HTML_JS}</script></body></html>
"""
