#!/usr/bin/env python3
"""Small CP-SAT call schedule solver for the NiceSchedule AI tutorial.

This is a teaching example, not a production scheduler. It keeps the rule set
small on purpose so a human or coding agent can understand and extend it.

The core idea:

1. Read structured CSV inputs.
2. Create a Boolean decision variable for each possible assignment.
3. Add hard constraints that must be true.
4. Add soft penalties for things we prefer to avoid.
5. Ask CP-SAT to minimize the total penalty.
6. Write the chosen assignments back to CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path

from ortools.sat.python import cp_model


@dataclass(frozen=True)
class CoverageRow:
    date: date
    shift_type: str
    required_count: int


@dataclass(frozen=True)
class RequestRow:
    request_id: str
    clinician_id: str
    start_date: date
    end_date: date
    request_type: str
    hard: bool
    shift_type: str | None
    note: str


def parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def parse_int(value: str, default: int = 0) -> int:
    value = (value or "").strip()
    return int(value) if value else default


def read_csv(path: Path) -> list[dict[str, str]]:
    # utf-8-sig strips the byte-order mark Excel writes when you "Save as CSV UTF-8".
    # Without this, the first header (e.g. clinician_id) shows up as "﻿clinician_id"
    # and every row lookup silently misses.
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def dates_between(start: date, end: date) -> list[date]:
    days = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def load_config(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def slugify(text: str) -> str:
    """Derive a stable, lowercase, alphanumeric+underscore key from a name.
    Used so users can leave clinician_id blank in clinicians.csv and have it
    derived from the name field, and so they can type names directly in
    requests.csv / history.csv."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def resolve_clinician_key(value: str, clinicians: dict[str, dict[str, str]]) -> str:
    """Map a request/history value to a canonical clinician_id. Matches
    direct ID first, then a slug of the value (so 'Alice Smith' resolves to
    'alice_smith'). Falls through unchanged so unknown-clinician errors
    still fire downstream."""
    value = value.strip()
    if not value or value in clinicians:
        return value
    slug = slugify(value)
    if slug in clinicians:
        return slug
    return value


def load_clinicians(path: Path) -> dict[str, dict[str, str]]:
    rows = read_csv(path)
    clinicians: dict[str, dict[str, str]] = {}
    for row in rows:
        clinician_id = row.get("clinician_id", "").strip()
        name = row.get("name", "").strip()
        if not clinician_id:
            if not name:
                raise ValueError(f"Row in {path} has no clinician_id and no name.")
            clinician_id = slugify(name)
            if not clinician_id:
                raise ValueError(
                    f"Could not derive a clinician_id from name {name!r} in {path}. "
                    "Fill in clinician_id explicitly."
                )
            row["clinician_id"] = clinician_id
        if clinician_id in clinicians:
            raise ValueError(f"Duplicate clinician_id {clinician_id!r}")
        if parse_bool(row.get("active", "1")):
            clinicians[clinician_id] = row
    return clinicians


def load_coverage(path: Path) -> list[CoverageRow]:
    rows = []
    for row in read_csv(path):
        rows.append(
            CoverageRow(
                date=parse_date(row["date"]),
                shift_type=row["shift_type"].strip().upper(),
                required_count=parse_int(row["required_count"], 1),
            )
        )
    rows.sort(key=lambda r: (r.date, r.shift_type))
    return rows


def load_requests(
    path: Path, clinicians: dict[str, dict[str, str]]
) -> list[RequestRow]:
    requests = []
    for row in read_csv(path):
        raw_shift = row.get("shift_type", "").strip().upper()
        hard_value = row.get("hard", "1").strip()
        clinician_id = resolve_clinician_key(row["clinician_id"], clinicians)
        requests.append(
            RequestRow(
                request_id=row["request_id"].strip(),
                clinician_id=clinician_id,
                start_date=parse_date(row["start_date"]),
                end_date=parse_date(row["end_date"]),
                request_type=row["request_type"].strip().lower(),
                hard=parse_bool(hard_value or "1"),
                shift_type=raw_shift or None,
                note=row.get("note", "").strip(),
            )
        )
    return requests


def load_history(
    path: Path, clinicians: dict[str, dict[str, str]]
) -> tuple[Counter[str], Counter[str], Counter[tuple[str, int]]]:
    total = Counter()
    weekend = Counter()
    weekday = Counter()
    if not path.exists():
        return total, weekend, weekday
    for row in read_csv(path):
        clinician_id = resolve_clinician_key(row["clinician_id"], clinicians)
        day = parse_date(row["date"])
        total[clinician_id] += 1
        if is_weekend(day):
            weekend[clinician_id] += 1
        weekday[(clinician_id, day.weekday())] += 1
    return total, weekend, weekday


def eligibility_column(shift_type: str) -> str:
    return "can_" + shift_type.lower().replace(" ", "_").replace("-", "_")


def request_matches(request: RequestRow, day: date, shift_type: str) -> bool:
    if not (request.start_date <= day <= request.end_date):
        return False
    return request.shift_type is None or request.shift_type == shift_type


def hard_block_label(request: RequestRow) -> str:
    if request.shift_type:
        return f"NO {request.shift_type}"
    if request.request_type == "vacation":
        return "VAC"
    if request.request_type == "no_call":
        return "NO CALL"
    return "BLOCK"


# Color pairs (background, ink) used by the HTML schedule renderer for each
# shift type. OR and OB match the sample article styling; common adaptations
# (NIGHT, BACKUP, CARDIAC, NORTH/SOUTH/EAST/WEST sites, ICU, TRAUMA, PEDS) get
# their own colors so the schedule renders nicely without code edits.
SHIFT_PALETTE = {
    "OR":      ("#e3edf5", "#1a4769"),
    "OB":      ("#f4e8d3", "#6e4a16"),
    "NIGHT":   ("#2d353d", "#fbfaf7"),
    "BACKUP":  ("#e7f2ed", "#2f6b57"),
    "CARDIAC": ("#f8e7e3", "#963c2f"),
    "NORTH":   ("#dfe6f0", "#2a4a73"),
    "SOUTH":   ("#ecdcd1", "#6e4a3a"),
    "EAST":    ("#e6efd9", "#4a6824"),
    "WEST":    ("#ead9ec", "#5a3a6e"),
    "ICU":     ("#d8e4ec", "#1a4969"),
    "TRAUMA":  ("#f4d8d6", "#7a2a22"),
    "PEDS":    ("#e6efd9", "#4a6824"),
}

# Stable fallback palette for any shift type not listed above. Picked by a
# deterministic hash of the shift name so the same shift always gets the same
# color across re-runs.
SHIFT_FALLBACK_PALETTE = [
    ("#e3edf5", "#1a4769"),
    ("#f4e8d3", "#6e4a16"),
    ("#e7f2ed", "#2f6b57"),
    ("#f8e7e3", "#963c2f"),
    ("#ddd6ec", "#4a3a6e"),
    ("#ecdcd1", "#6e4a3a"),
    ("#d8e4ec", "#1a4969"),
    ("#f4d8d6", "#7a2a22"),
]

# Vacation and other hard blocks are visually distinct in the HTML output.
# Neutral, professional tones that print well and look "official".
VACATION_BG = "#f4f1e8"
VACATION_INK = "#4a4a4a"
VACATION_RULE = "#d1cdbc"
BLOCK_BG = "#f8f9fa"
BLOCK_INK = "#495057"
BLOCK_RULE = "#ced4da"


def hard_block_kind(request: RequestRow) -> str:
    return "vacation" if request.request_type == "vacation" else "block"


def shift_colors(shift_type: str) -> tuple[str, str]:
    key = shift_type.upper()
    if key in SHIFT_PALETTE:
        return SHIFT_PALETTE[key]
    idx = sum(ord(c) for c in key) % len(SHIFT_FALLBACK_PALETTE)
    return SHIFT_FALLBACK_PALETTE[idx]


def shift_css_class(shift_type: str) -> str:
    # Prefix avoids collisions with built-in CSS class names and HTML elements.
    return "s-" + shift_type.lower().replace(" ", "_").replace("-", "_")


def write_html_schedule(
    output_path: Path,
    coverage: list[CoverageRow],
    clinicians: dict[str, dict[str, str]],
    assignments: list[dict[str, str]],
    requests: list[RequestRow],
):
    all_dates = sorted({c.date for c in coverage})
    if not all_dates:
        return

    clinician_ids = sorted(clinicians.keys(), key=lambda cid: clinicians[cid]["name"])
    num_days = len(all_dates)

    assignment_map: dict[tuple[date, str], list[str]] = defaultdict(list)
    for a in assignments:
        d = datetime.strptime(a["date"], "%Y-%m-%d").date()
        assignment_map[(d, a["clinician_id"])].append(a["shift_type"])

    hard_block_map: dict[tuple[date, str], list[tuple[str, str]]] = defaultdict(list)
    for r in requests:
        if r.hard:
            for d in dates_between(r.start_date, r.end_date):
                label = hard_block_label(r)
                item = (label, hard_block_kind(r))
                items = hard_block_map[(d, r.clinician_id)]
                if item not in items:
                    items.append(item)

    totals: dict[str, int] = defaultdict(int)
    weekend_totals: dict[str, int] = defaultdict(int)
    for (d, cid), shifts in assignment_map.items():
        totals[cid] += len(shifts)
        if is_weekend(d):
            weekend_totals[cid] += len(shifts)

    soft_violations: list[tuple[RequestRow, date, str]] = []
    for r in requests:
        if r.hard:
            continue
        for d in dates_between(r.start_date, r.end_date):
            for shift in assignment_map.get((d, r.clinician_id), []):
                if r.shift_type is None or r.shift_type == shift:
                    soft_violations.append((r, d, shift))

    shift_types = sorted({c.shift_type for c in coverage})

    shift_css = ""
    for st in shift_types:
        bg, ink = shift_colors(st)
        cls = shift_css_class(st)
        # Screen: tinted bg + inset frame.
        # Default print: text only — no border, no bg. Chiefs read the cell
        #   label ("OR" / "OB") directly; identification doesn't need color.
        # "Print in color" (body.print-color): force-print the screen styling.
        shift_css += (
            f"    .gcell.{cls} {{ background: {bg}; color: {ink}; box-shadow: inset 0 0 0 1px {ink}33; font-weight: 700; }}\n"
            f"    .swatch.{cls} {{ background: {bg}; border: 1px solid {ink}44; }}\n"
            f"    @media print {{ .gcell.{cls} {{ background: white !important; color: black !important; box-shadow: none !important; }} }}\n"
            f"    @media print {{ body.print-color .gcell.{cls} {{ background: {bg} !important; color: {ink} !important; box-shadow: inset 0 0 0 1px {ink}33 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }} }}\n"
        )
    shift_css += (
        f"    .gcell.vacation {{ background: {VACATION_BG}; color: {VACATION_INK}; box-shadow: inset 0 0 0 1px {VACATION_RULE}; font-weight: 700; }}\n"
        f"    .swatch.vacation {{ background: {VACATION_BG}; border: 1px solid {VACATION_INK}55; }}\n"
        f"    .gcell.block {{ background: {BLOCK_BG}; color: {BLOCK_INK}; box-shadow: inset 0 0 0 1px {BLOCK_RULE}; font-weight: 700; }}\n"
        f"    .swatch.block {{ background: {BLOCK_BG}; border: 1px solid {BLOCK_INK}55; }}\n"
        f"    @media print {{\n"
        f"      .gcell.vacation {{ background: white !important; color: black !important; box-shadow: none !important; font-style: italic; }}\n"
        f"      .gcell.block {{ background: white !important; color: black !important; box-shadow: none !important; }}\n"
        f"      body.print-color .gcell.vacation {{ background: {VACATION_BG} !important; color: {VACATION_INK} !important; box-shadow: inset 0 0 0 1px {VACATION_RULE} !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; font-style: italic; }}\n"
        f"      body.print-color .gcell.block {{ background: {BLOCK_BG} !important; color: {BLOCK_INK} !important; box-shadow: inset 0 0 0 1px {BLOCK_RULE} !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}\n"
        f"    }}\n"
    )

    # Header row.
    header_html = '<div class="gh corner">Clinician</div>\n'
    for d in all_dates:
        weekend_cls = " weekend" if is_weekend(d) else ""
        header_html += f'<div class="gh{weekend_cls}">{d.strftime("%a %-d")}</div>\n'
    header_html += '<div class="gh totals col-total">Total</div>\n'
    header_html += '<div class="gh totals col-weekend">Weekend</div>\n'

    # Clinician rows.
    rows_html = ""
    for cid in clinician_ids:
        rows_html += f'<div class="gname">{escape(clinicians[cid]["name"])}</div>\n'
        for d in all_dates:
            weekend_cls = " weekend" if is_weekend(d) else ""
            shifts = assignment_map.get((d, cid), [])
            hard_blocks = hard_block_map.get((d, cid), [])

            if shifts:
                label = " / ".join(shifts)
                cls = shift_css_class(shifts[0])
                rows_html += f'<div class="gcell{weekend_cls} {cls}">{escape(label)}</div>\n'
            elif hard_blocks:
                label = " / ".join(label for label, _kind in hard_blocks)
                block_kind = "vacation" if any(kind == "vacation" for _label, kind in hard_blocks) else "block"
                rows_html += f'<div class="gcell{weekend_cls} {block_kind}">{escape(label)}</div>\n'
            else:
                rows_html += f'<div class="gcell{weekend_cls} empty"></div>\n'

        target = parse_int(clinicians[cid].get("target_shifts", ""), 0)
        weekend_target = parse_int(clinicians[cid].get("target_weekend_shifts", ""), 0)
        total = totals[cid]
        weekend = weekend_totals[cid]

        total_inner = f'{total}<span class="target">/{target}</span>' if target else f'{total}'
        rows_html += f'<div class="gtotal col-total">{total_inner}</div>\n'
        weekend_inner = f'{weekend}<span class="target">/{weekend_target}</span>' if weekend_target else f'{weekend}'
        rows_html += f'<div class="gtotal col-weekend">{weekend_inner}</div>\n'

    # Legend.
    legend_items = ""
    for st in shift_types:
        cls = shift_css_class(st)
        legend_items += f'<span class="lg"><span class="swatch {cls}"></span> {escape(st)} call</span>\n'
    legend_items += '<span class="lg"><span class="swatch vacation"></span> Vacation</span>\n'
    legend_items += '<span class="lg"><span class="swatch block"></span> No-call / hard block</span>\n'

    # Notes.
    notes_items = ""
    for r, d, shift in soft_violations:
        name = escape(clinicians.get(r.clinician_id, {}).get("name", r.clinician_id))
        when = d.strftime("%a %b %-d")
        type_label = escape(r.request_type.replace("_", " "))
        note_suffix = f" <em>{escape(r.note)}</em>" if r.note else ""
        notes_items += f"<li>{name} — {type_label} on {when} not honored; covering {escape(shift)}.{note_suffix}</li>\n"
    notes_html = f'<section class="schedule-notes"><h2>Notes</h2><ul>{notes_items}</ul></section>' if notes_items else ""

    css = (
        """
    :root {
      --bg: #ffffff;
      --ink: #000000;
      --muted: #666666;
      --rule: #dddddd;
      --rule-strong: #000000;
      --weekend: #f5f5f5;
      --font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    }
    body {
      margin: 0;
      padding: 40px;
      background: var(--bg);
      color: var(--ink);
      font-family: var(--font-sans);
      font-size: 13px;
      line-height: 1.2;
    }
    *, *::before, *::after { box-sizing: border-box; }
    .container { max-width: 1600px; margin: 0 auto; }
    header {
      border-bottom: 2px solid var(--ink);
      padding-bottom: 12px;
      margin-bottom: 24px;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
    }
    h1 { font-size: 20px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.05em; margin: 0; }
    .subtitle { color: var(--muted); font-size: 12px; font-weight: 600; text-transform: uppercase; }

    .grid-frame { border: 1px solid var(--rule-strong); background: #fff; }
    .grid-frame-scroll { overflow-x: auto; }
    .grid-schedule {
      display: grid;
      grid-template-columns: 140px repeat(var(--n-days), minmax(48px, 1fr)) 60px 60px;
      width: max-content;
      min-width: 100%;
    }
    .gh {
      padding: 8px 4px;
      border-bottom: 1px solid var(--rule-strong);
      border-right: 1px solid var(--rule);
      background: #fcfcfc;
      font-size: 10px;
      font-weight: 800;
      text-transform: uppercase;
      text-align: center;
    }
    .gh.corner { text-align: left; padding-left: 12px; position: sticky; left: 0; z-index: 3; }
    .gh.col-total { position: sticky; right: 60px; z-index: 3; }
    .gh.col-weekend { position: sticky; right: 0; z-index: 3; }
    .gh.weekend { background: var(--weekend); }

    .gname {
      display: flex;
      align-items: center;
      padding: 10px 12px;
      border-bottom: 1px solid var(--rule);
      border-right: 2px solid var(--rule-strong);
      background: #fff;
      font-weight: 700;
      position: sticky;
      left: 0;
      z-index: 2;
    }
    .gcell {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      padding: 4px;
      border-bottom: 1px solid var(--rule);
      border-right: 1px solid var(--rule);
    }
    .gcell.weekend { background: #fafafa; }
    .gcell.empty { color: #eee; }

    .gtotal {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 8px 4px;
      border-bottom: 1px solid var(--rule);
      border-left: 2px solid var(--rule-strong);
      background: #fff;
      font-weight: 800;
      position: sticky;
      z-index: 2;
    }
    .gtotal.col-total { right: 60px; }
    .gtotal.col-weekend { right: 0; border-left: 1px solid var(--rule); }
    .gtotal .target { color: var(--muted); font-size: 9px; font-weight: 400; margin-left: 2px; }

    .grid-legend { display: flex; flex-wrap: wrap; gap: 20px; margin: 24px 0; font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--muted); }
    .lg { display: inline-flex; align-items: center; gap: 6px; }
    .swatch { width: 12px; height: 12px; border: 1px solid #ccc; }

    .schedule-notes { margin-top: 24px; padding: 16px; border: 1px solid var(--rule); font-size: 12px; }
    .schedule-notes h2 { font-size: 11px; font-weight: 900; text-transform: uppercase; margin: 0 0 8px; }

    /* Branding band lives INSIDE .grid-frame so a chief who tries to crop
       it off the printout has to slice into the schedule box itself. */
    .grid-watermark {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 12px;
      border-top: 1px solid var(--rule);
      background: #fcfcfc;
      color: var(--muted);
      font-size: 10px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }
    .grid-watermark a {
      color: var(--ink);
      text-decoration: none;
      font-weight: 800;
    }

    .print-actions { margin-bottom: 24px; display: flex; gap: 12px; }
    .btn-subtle {
      padding: 4px 10px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      background: #eee;
      color: #333;
      border: 1px solid #ddd;
      cursor: pointer;
    }
    .btn-subtle:hover { background: #ddd; }

    @media print {
      @page { size: landscape; margin: 0.4in; }
      body { padding: 0; font-size: 9px; }
      .container { max-width: none; }
      .print-actions { display: none; }
      header { border-bottom-width: 1.5pt; margin-bottom: 12pt; }
      .grid-frame { border-width: 0.75pt; }
      /* Without this the scroll container stays at overflow-x:auto and the
         grid renders at its max-content width — the right edge (Total +
         Weekend columns and any days past ~8) falls off the page. */
      .grid-frame-scroll { overflow: visible; }
      /* Default print: hide the legend (swatches are colorless without
         print-color-adjust). In "Print in color" mode we restore it. */
      .grid-legend { display: none; }
      body.print-color .grid-legend { display: flex; }
      body.print-color .swatch {
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }
      .grid-schedule {
        grid-template-columns: 80px repeat(var(--n-days), minmax(0, 1fr)) 36px 40px;
        width: 100%;
      }
      .gh { padding: 4px 2px; font-size: 8px; border-width: 0.5pt; position: static; }
      .gname { padding: 4px; font-size: 8px; position: static; border-width: 0.5pt; border-right-width: 1.2pt; }
      .gcell { min-height: 20px; padding: 1px; border-width: 0.5pt; }
      .gtotal { padding: 2px; font-size: 8px; position: static; border-width: 0.5pt; border-left-width: 1.2pt; }
      .gh, .gname, .gcell, .gtotal, .gh.weekend, .gcell.weekend { background: white !important; }
      .schedule-notes { page-break-inside: avoid; border-width: 0.5pt; }
      body.print-color .grid-legend { margin: 12pt 0; }
      .grid-watermark {
        padding: 4pt 8pt;
        border-top-width: 0.5pt;
        font-size: 7pt;
        background: white !important;
      }
    }
"""
        + shift_css
        + """
    </style>"""
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Call Schedule | NiceSchedule</title>
    <style>{css}</style>
</head>
<body>
    <div class="container">
        <div class="print-actions">
            <button class="btn-subtle" onclick="window.print()">Print Schedule</button>
            <button class="btn-subtle" onclick="printInColor()">Print in Color</button>
        </div>
        <script>
            function printInColor() {{
                document.body.classList.add('print-color');
                window.print();
            }}
            window.addEventListener('afterprint', function () {{
                document.body.classList.remove('print-color');
            }});
        </script>
        <header>
            <div class="header-copy">
                <h1>Call Schedule</h1>
                <div class="subtitle">{all_dates[0].strftime('%B %-d')} &ndash; {all_dates[-1].strftime('%B %-d, %Y')}</div>
            </div>
        </header>

        <div class="grid-frame">
            <div class="grid-frame-scroll">
                <div class="grid-schedule" style="--n-days: {num_days};">
                    {header_html}
                    {rows_html}
                </div>
            </div>
            <div class="grid-watermark">
                <span>{all_dates[0].strftime('%B %-d')} &ndash; {all_dates[-1].strftime('%B %-d, %Y')}</span>
                <span>Built with <a href="https://niceschedule.com">NiceSchedule.com</a></span>
            </div>
        </div>

        <div class="grid-legend">
            {legend_items}
        </div>

        {notes_html}
    </div>
</body>
</html>
"""
    with output_path.open("w") as f:
        f.write(html)


def solve(config_path: Path, verbose: bool = False) -> int:
    # The config file tells the solver where to find input CSVs, where to write
    # output, and how strongly to weight soft preferences.
    config = load_config(config_path)
    base_dir = config_path.parent.parent
    input_dir = base_dir / config["input_dir"]
    output_path = base_dir / config.get("output_csv", "output/schedule.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    clinicians = load_clinicians(input_dir / "clinicians.csv")
    coverage = load_coverage(input_dir / "coverage.csv")
    requests = load_requests(input_dir / "requests.csv", clinicians)
    history_total, history_weekend, history_weekday = load_history(input_dir / "history.csv", clinicians)

    if not clinicians:
        raise ValueError("No active clinicians found.")
    if not coverage:
        raise ValueError("No coverage rows found.")

    for clinician_id in set(history_total) | set(history_weekend):
        if clinician_id not in clinicians:
            raise ValueError(
                f"history.csv references unknown clinician {clinician_id!r}."
            )

    # Every shift type in coverage.csv needs a matching eligibility column in
    # clinicians.csv. For example, OR expects can_or and OB expects can_ob.
    # This lets people add new shift types without changing code immediately.
    shift_types = sorted({row.shift_type for row in coverage})
    for shift_type in shift_types:
        column = eligibility_column(shift_type)
        missing = [cid for cid, row in clinicians.items() if column not in row]
        if missing:
            raise ValueError(
                f"Missing eligibility column {column!r} for shift type {shift_type!r}."
            )

    rules = config.get("rules", {})
    weights = rules.get("weights", {})
    default_min_gap = parse_int(str(rules.get("min_days_between_assignments_default", 1)))
    preferred_gap = parse_int(str(rules.get("preferred_days_between_assignments", 3)))

    model = cp_model.CpModel()
    coverage_ids = list(range(len(coverage)))
    clinician_ids = sorted(clinicians)

    # Decision variables:
    #
    # x[(coverage row, clinician)] is 1 if that clinician is assigned to that
    # required shift, otherwise 0.
    #
    # Example:
    #   x[(June 1 OB, Dr. Fox)] = 1 means Dr. Fox covers OB on June 1.
    x = {}
    for cov_id, cov in enumerate(coverage):
        for clinician_id in clinician_ids:
            x[(cov_id, clinician_id)] = model.NewBoolVar(
                f"assign_{cov.date}_{cov.shift_type}_{clinician_id}"
            )

    # HARD RULE 1:
    # Cover every required shift.
    #
    # If coverage.csv says June 1 needs one OB clinician, exactly one assignment
    # variable for that row must be selected.
    for cov_id, cov in enumerate(coverage):
        model.Add(sum(x[(cov_id, cid)] for cid in clinician_ids) == cov.required_count)

    # HARD RULE 2:
    # Only assign clinicians to shifts they are eligible to cover.
    #
    # If can_ob is 0, that clinician can never be assigned to OB rows.
    for cov_id, cov in enumerate(coverage):
        column = eligibility_column(cov.shift_type)
        for clinician_id in clinician_ids:
            if not parse_bool(clinicians[clinician_id].get(column, "0")):
                model.Add(x[(cov_id, clinician_id)] == 0)

    coverage_by_date: dict[date, list[int]] = defaultdict(list)
    for cov_id, cov in enumerate(coverage):
        coverage_by_date[cov.date].append(cov_id)

    day_assigned = {}
    for day, cov_ids in coverage_by_date.items():
        for clinician_id in clinician_ids:
            # day_assigned is 1 if the clinician works any shift that day.
            # Because it is a BoolVar and equals the sum of that person's daily
            # assignments, it also enforces at most one assignment per day.
            var = model.NewBoolVar(f"works_{day}_{clinician_id}")
            model.Add(var == sum(x[(cov_id, clinician_id)] for cov_id in cov_ids))
            day_assigned[(day, clinician_id)] = var

    # HARD RULE 3 and SOFT PREFERENCE 1:
    # Honor hard requests, try to honor soft requests, and pin locks.
    #
    # request_type=lock means the clinician MUST cover that (date, shift_type)
    # row. shift_type is required on locks — pinning to "anything that day"
    # isn't meaningful. Locks are always hard.
    #
    # Otherwise:
    # - hard=1 means the assignment is blocked.
    # - hard=0 means the solver may assign the clinician, but pays a penalty.
    objective_terms = []
    soft_request_weight = parse_int(str(weights.get("soft_request_violation", 25)))
    for request in requests:
        if request.clinician_id not in clinicians:
            raise ValueError(
                f"Request {request.request_id!r} references unknown clinician "
                f"{request.clinician_id!r}."
            )
        if request.request_type == "lock" and request.shift_type is None:
            raise ValueError(
                f"Lock request {request.request_id!r} must set shift_type."
            )
        matched_any = False
        for cov_id, cov in enumerate(coverage):
            if not request_matches(request, cov.date, cov.shift_type):
                continue
            matched_any = True
            var = x[(cov_id, request.clinician_id)]
            if request.request_type == "lock":
                model.Add(var == 1)
            elif request.hard:
                model.Add(var == 0)
            else:
                objective_terms.append(soft_request_weight * var)
        if request.request_type == "lock" and not matched_any:
            raise ValueError(
                f"Lock request {request.request_id!r} did not match any "
                f"coverage row for {request.clinician_id} on "
                f"{request.start_date}..{request.end_date} "
                f"shift_type={request.shift_type}. Check the date and shift_type "
                "against coverage.csv."
            )

    all_dates = sorted(coverage_by_date)

    # Per-clinician assignment limits and fairness goals.
    target_weight = parse_int(str(weights.get("target_deviation", 100)))
    weekend_weight = parse_int(str(weights.get("weekend_deviation", 35)))
    max_assignments_possible = len(coverage)

    assigned_count = {}
    weekend_count = {}
    for clinician_id in clinician_ids:
        assigned_expr = sum(x[(cov_id, clinician_id)] for cov_id in coverage_ids)
        weekend_expr = sum(
            x[(cov_id, clinician_id)]
            for cov_id, cov in enumerate(coverage)
            if is_weekend(cov.date)
        )
        assigned_count[clinician_id] = assigned_expr
        weekend_count[clinician_id] = weekend_expr

        # HARD RULE 4:
        # Respect maximum total shifts and maximum weekend shifts.
        max_shifts = parse_int(clinicians[clinician_id].get("max_shifts", ""), 999)
        max_weekends = parse_int(
            clinicians[clinician_id].get("max_weekend_shifts", ""), 999
        )
        model.Add(assigned_expr <= max_shifts)
        model.Add(weekend_expr <= max_weekends)

        # SOFT PREFERENCE 2:
        # Try to land near each clinician's target shift count.
        #
        # CP-SAT cannot directly minimize abs(assigned - target), so we model
        # "over" and "under" variables where:
        #   assigned - target = over - under
        # Then minimizing over + under minimizes the absolute deviation.
        target = parse_int(clinicians[clinician_id].get("target_shifts", ""), 0)
        over = model.NewIntVar(0, max_assignments_possible, f"over_target_{clinician_id}")
        under = model.NewIntVar(
            0, max_assignments_possible, f"under_target_{clinician_id}"
        )
        model.Add(assigned_expr - target == over - under)
        objective_terms.append(target_weight * (over + under))

        # SOFT PREFERENCE 3:
        # Same idea, but for weekend assignments.
        weekend_target = parse_int(
            clinicians[clinician_id].get("target_weekend_shifts", ""), 0
        )
        weekend_over = model.NewIntVar(
            0, max_assignments_possible, f"over_weekend_{clinician_id}"
        )
        weekend_under = model.NewIntVar(
            0, max_assignments_possible, f"under_weekend_{clinician_id}"
        )
        model.Add(weekend_expr - weekend_target == weekend_over - weekend_under)
        objective_terms.append(weekend_weight * (weekend_over + weekend_under))

    # SOFT PREFERENCE 4:
    # Balance current assignments plus historical burden.
    #
    # If someone already carried more call last month, the solver should avoid
    # increasing that gap unless coverage requires it.
    history_weight = parse_int(str(weights.get("history_balance", 40)))
    max_total = model.NewIntVar(0, 1000, "max_total_burden")
    min_total = model.NewIntVar(0, 1000, "min_total_burden")
    for clinician_id in clinician_ids:
        total_expr = assigned_count[clinician_id] + history_total[clinician_id]
        model.Add(total_expr <= max_total)
        model.Add(total_expr >= min_total)
    objective_terms.append(history_weight * (max_total - min_total))

    # SOFT PREFERENCE 5:
    # Spread weekday patterns across months. Penalize giving a clinician a
    # weekday they've already covered a lot in history.csv. Pulls apart
    # stagnation patterns like "Cary always gets Mondays" over time. No-op
    # on a first-month solve (history_weekday is empty). sample_rules.json
    # sets this weight to 0 so the article's sample output stays stable;
    # my_rules.template.json sets 20 so real groups get the term active.
    weekday_repeat_weight = parse_int(str(weights.get("weekday_repeat", 20)))
    for clinician_id in clinician_ids:
        for weekday in range(7):
            prior = history_weekday[(clinician_id, weekday)]
            if prior == 0:
                continue
            same_weekday_now = sum(
                x[(cov_id, clinician_id)]
                for cov_id, cov in enumerate(coverage)
                if cov.date.weekday() == weekday
            )
            objective_terms.append(weekday_repeat_weight * prior * same_weekday_now)

    # HARD RULE 5 and SOFT PREFERENCE 6:
    # Enforce minimum rest, then prefer more spacing when possible.
    #
    # min_days_between_assignments is hard. If min gap is 1, someone cannot work
    # Monday and Tuesday.
    #
    # preferred_days_between_assignments is soft. If preferred gap is 3, the
    # solver pays a small penalty for assignments that are 2 or 3 days apart,
    # but it may still use them when that is the best feasible schedule.
    rest_weight = parse_int(str(weights.get("rest_spacing", 5)))
    for clinician_id in clinician_ids:
        min_gap = parse_int(
            clinicians[clinician_id].get("min_days_between_assignments", ""),
            default_min_gap,
        )
        for i, day_a in enumerate(all_dates):
            for day_b in all_dates[i + 1 :]:
                gap = (day_b - day_a).days
                if gap > preferred_gap:
                    break
                a = day_assigned[(day_a, clinician_id)]
                b = day_assigned[(day_b, clinician_id)]
                if gap <= min_gap:
                    model.Add(a + b <= 1)
                else:
                    both = model.NewBoolVar(f"close_{day_a}_{day_b}_{clinician_id}")
                    model.Add(both <= a)
                    model.Add(both <= b)
                    model.Add(both >= a + b - 1)
                    objective_terms.append(rest_weight * (preferred_gap + 1 - gap) * both)

    # The objective is the total penalty across all soft preferences. Hard rules
    # are not in the objective because they are mandatory.
    model.Minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60
    # Reproducible by default: same inputs always produce the same schedule on
    # any machine. That lets the article show a specific arrangement and have
    # it actually match what a reader gets when they run the solver.
    # interleave_search + random_seed makes parallel search deterministic;
    # without interleave_search, 8 workers are faster but non-reproducible.
    solver.parameters.num_search_workers = 8
    solver.parameters.random_seed = 1
    solver.parameters.interleave_search = True
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("No feasible schedule found.")
        print("Try relaxing max_shifts, max_weekend_shifts, rest gaps, or hard requests.")
        return 2

    # Convert selected assignment variables back into rows a human can inspect.
    rows = []
    for cov_id, cov in enumerate(coverage):
        for clinician_id in clinician_ids:
            if solver.Value(x[(cov_id, clinician_id)]) == 1:
                rows.append(
                    {
                        "date": cov.date.isoformat(),
                        "shift_type": cov.shift_type,
                        "clinician_id": clinician_id,
                        "name": clinicians[clinician_id]["name"],
                    }
                )

    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["date", "shift_type", "clinician_id", "name"]
        )
        writer.writeheader()
        writer.writerows(rows)

    # Generate HTML version
    html_output_path = output_path.with_suffix(".html")
    write_html_schedule(html_output_path, coverage, clinicians, rows, requests)

    status_name = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
    print(f"Status: {status_name}")
    if verbose:
        print(f"Objective: {solver.ObjectiveValue():.0f}")
    print(f"Wrote {len(rows)} assignments to {output_path}")
    print()
    print("Assignment summary:")
    for clinician_id in clinician_ids:
        current = int(solver.Value(assigned_count[clinician_id]))
        weekends = int(solver.Value(weekend_count[clinician_id]))
        prior = history_total[clinician_id]
        print(
            f"  {clinicians[clinician_id]['name']}: "
            f"{current} current, {weekends} weekend, {prior} prior"
        )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="config/sample_rules.json",
        help="Path to JSON config, relative to this folder or absolute.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print solver diagnostics such as the objective score.",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = Path(__file__).resolve().parent / config_path
    return solve(config_path, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
