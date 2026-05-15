#!/usr/bin/env python3
"""HTML rendering for the call schedule.

Kept separate from solver.py so the solver file stays focused on the model
(decision variables, hard rules, soft preferences). Edit this file when you
want to change how the printable schedule looks; edit solver.py when you want
to change how the schedule is built.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from html import escape
from pathlib import Path

from solver import (
    CoverageRow,
    RequestRow,
    dates_between,
    is_weekend,
    parse_int,
)


def hard_block_label(request: RequestRow) -> str:
    if request.shift_type:
        return f"NO {request.shift_type}"
    if request.request_type == "vacation":
        return "VAC"
    if request.request_type == "no_call":
        return "NO CALL"
    return "BLOCK"


def hard_block_kind(request: RequestRow) -> str:
    return "vacation" if request.request_type == "vacation" else "block"


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


SOFT_REQUEST_PHRASE = {
    "vacation": "vacation",
    "no_call": "no-call request",
    "prefer_off": "preference to be off",
}


def shift_colors(shift_type: str) -> tuple[str, str]:
    key = shift_type.upper()
    if key in SHIFT_PALETTE:
        return SHIFT_PALETTE[key]
    idx = sum(ord(c) for c in key) % len(SHIFT_FALLBACK_PALETTE)
    return SHIFT_FALLBACK_PALETTE[idx]


def shift_css_class(shift_type: str) -> str:
    # Prefix avoids collisions with built-in CSS class names and HTML elements.
    return "s-" + shift_type.lower().replace(" ", "_").replace("-", "_")


def build_schedule_summary(
    clinicians: dict[str, dict[str, str]],
    assignments: list[dict[str, str]],
    requests: list[RequestRow],
    history_total: Counter[str],
    totals: dict[str, int],
    weekend_totals: dict[str, int],
    soft_violations: list[tuple[RequestRow, date, str]],
) -> list[str]:
    """Plain-English bullets describing what the solver did. Rendered below
    the grid as a chief-facing review pane (hidden on print)."""
    bullets: list[str] = []

    n_shifts = len(assignments)
    n_active = sum(1 for cid in clinicians if totals.get(cid, 0) > 0)
    bullets.append(f"Filled all {n_shifts} shifts across {n_active} clinicians.")

    hard_blocks = [r for r in requests if r.hard and r.request_type != "lock"]
    if hard_blocks:
        word = "request" if len(hard_blocks) == 1 else "requests"
        bullets.append(f"All {len(hard_blocks)} time-off {word} honored.")

    locks = [r for r in requests if r.request_type == "lock"]
    if len(locks) > 3:
        bullets.append(f"{len(locks)} pre-set assignments locked in place.")
    else:
        for r in locks:
            name = clinicians.get(r.clinician_id, {}).get("name", r.clinician_id)
            if r.start_date == r.end_date:
                when = r.start_date.strftime("%a %b %-d")
            else:
                when = f"{r.start_date.strftime('%b %-d')}–{r.end_date.strftime('%b %-d')}"
            bullets.append(f"{name} pinned to {r.shift_type} on {when}.")

    active_totals = [totals[cid] for cid in clinicians if totals.get(cid, 0) > 0]
    if len(active_totals) >= 2:
        spread = max(active_totals) - min(active_totals)
        if spread == 0:
            bullets.append("Every clinician got the exact same number of shifts.")
        elif spread == 1:
            bullets.append(
                "Workload is within 1 shift across everyone — the tightest spread possible."
            )

    callouts: list[str] = []
    for cid in sorted(clinicians, key=lambda c: clinicians[c]["name"]):
        name = clinicians[cid]["name"]
        assigned = totals.get(cid, 0)
        weekend = weekend_totals.get(cid, 0)
        max_shifts = parse_int(clinicians[cid].get("max_shifts", ""), 999)
        max_weekend = parse_int(clinicians[cid].get("max_weekend_shifts", ""), 999)
        target = parse_int(clinicians[cid].get("target_shifts", ""), 0)
        if max_shifts < 999 and assigned >= max_shifts:
            callouts.append(f"{name} hit their max of {max_shifts} shifts.")
        elif target and target - assigned >= 2:
            callouts.append(f"{name} came in under target ({assigned} of {target}).")
        elif target and assigned - target >= 1:
            callouts.append(f"{name} went over target ({assigned} vs {target}).")
        if max_weekend < 999 and weekend >= max_weekend:
            callouts.append(f"{name} hit their weekend max of {max_weekend}.")
    bullets.extend(callouts[:5])

    if history_total and totals:
        top_cid, top_prior = max(history_total.items(), key=lambda kv: kv[1])
        if top_cid in clinicians and top_prior > 0:
            this_month = totals.get(top_cid, 0)
            avg = sum(totals.values()) / max(len(totals), 1)
            if this_month < top_prior and this_month <= avg:
                name = clinicians[top_cid]["name"]
                bullets.append(
                    f"{name} carried the most call last month ({top_prior} shifts); "
                    f"got a lighter load this month ({this_month}) so the stacking doesn't repeat."
                )

    for r, d, shift in soft_violations:
        name = clinicians.get(r.clinician_id, {}).get("name", r.clinician_id)
        when = d.strftime("%a %b %-d")
        phrase = SOFT_REQUEST_PHRASE.get(r.request_type, r.request_type.replace("_", " "))
        suffix = f" ({r.note})" if r.note else ""
        bullets.append(
            f"Couldn't honor {name}'s {phrase} on {when} — covered {shift}.{suffix}"
        )

    return bullets


def write_html_schedule(
    output_path: Path,
    coverage: list[CoverageRow],
    clinicians: dict[str, dict[str, str]],
    assignments: list[dict[str, str]],
    requests: list[RequestRow],
    history_total: Counter[str],
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

    summary_bullets = build_schedule_summary(
        clinicians, assignments, requests, history_total, totals, weekend_totals, soft_violations
    )
    summary_items = "".join(f"<li>{escape(b)}</li>\n" for b in summary_bullets)
    summary_html = (
        f'<section class="schedule-summary"><h2>Summary</h2><ul>{summary_items}</ul></section>'
        if summary_items
        else ""
    )

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

    .schedule-summary {
      margin-top: 24px;
      padding: 14px 18px;
      border: 1px solid var(--rule);
      border-left: 3px solid #1a4769;
      background: #fcfcfa;
      font-size: 13px;
    }
    .schedule-summary h2 {
      font-size: 10px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin: 0 0 8px;
      color: var(--muted);
    }
    .schedule-summary ul { margin: 0; padding-left: 18px; }
    .schedule-summary li { margin: 4px 0; line-height: 1.45; }

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
      /* Summary is a chief-facing review pane — the printout is for the
         group and stays focused on the grid. */
      .schedule-summary { display: none; }
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

        {summary_html}
    </div>
</body>
</html>
"""
    with output_path.open("w") as f:
        f.write(html)
