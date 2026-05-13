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
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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


def load_clinicians(path: Path) -> dict[str, dict[str, str]]:
    rows = read_csv(path)
    clinicians: dict[str, dict[str, str]] = {}
    for row in rows:
        clinician_id = row["clinician_id"].strip()
        if not clinician_id:
            raise ValueError(f"Missing clinician_id in {path}")
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


def load_requests(path: Path) -> list[RequestRow]:
    requests = []
    for row in read_csv(path):
        raw_shift = row.get("shift_type", "").strip().upper()
        requests.append(
            RequestRow(
                request_id=row["request_id"].strip(),
                clinician_id=row["clinician_id"].strip(),
                start_date=parse_date(row["start_date"]),
                end_date=parse_date(row["end_date"]),
                request_type=row["request_type"].strip().lower(),
                hard=parse_bool(row.get("hard", "1")),
                shift_type=raw_shift or None,
                note=row.get("note", "").strip(),
            )
        )
    return requests


def load_history(path: Path) -> tuple[Counter[str], Counter[str]]:
    total = Counter()
    weekend = Counter()
    if not path.exists():
        return total, weekend
    for row in read_csv(path):
        clinician_id = row["clinician_id"].strip()
        day = parse_date(row["date"])
        total[clinician_id] += 1
        if is_weekend(day):
            weekend[clinician_id] += 1
    return total, weekend


def eligibility_column(shift_type: str) -> str:
    return "can_" + shift_type.lower().replace(" ", "_").replace("-", "_")


def request_matches(request: RequestRow, day: date, shift_type: str) -> bool:
    if not (request.start_date <= day <= request.end_date):
        return False
    return request.shift_type is None or request.shift_type == shift_type


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

VAC_COLORS = ("#efe9da", "#8a6a2e")


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

    vacation_map: dict[tuple[date, str], bool] = {}
    for r in requests:
        if r.hard:
            for d in dates_between(r.start_date, r.end_date):
                vacation_map[(d, r.clinician_id)] = True

    # Shift types actually present in this schedule, in display order.
    shift_types = sorted({c.shift_type for c in coverage})

    # Per-shift CSS — generated from the palette so adaptations get colors for free.
    shift_css = ""
    for st in shift_types:
        bg, ink = shift_colors(st)
        cls = shift_css_class(st)
        shift_css += (
            f"    .gcell.{cls} {{ background: {bg}; color: {ink}; "
            f"font-weight: 700; }}\n"
            f"    .swatch.{cls} {{ background: {bg}; border-color: {ink}33; }}\n"
        )
    vac_bg, vac_ink = VAC_COLORS
    shift_css += (
        f"    .gcell.vac {{ background: {vac_bg}; color: {vac_ink}; "
        f"font-weight: 700; font-style: italic; }}\n"
        f"    .swatch.vac {{ background: {vac_bg}; border-color: {vac_ink}55; }}\n"
    )

    css = (
        """
    :root {
      --bg: #fbfaf7;
      --panel: #ffffff;
      --panel-soft: #f4f1e8;
      --ink: #101418;
      --muted: #66717a;
      --rule: #e2dccf;
      --rule-2: #eee8dc;
      --accent: #153f63;
      --font-sans: "Inter", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    }
    body {
      margin: 0;
      padding: 40px 20px;
      background: var(--bg);
      color: var(--ink);
      font-family: var(--font-sans);
    }
    .container { max-width: 1200px; margin: 0 auto; }
    header { margin-bottom: 30px; }
    h1 { font-size: 24px; margin: 0 0 8px; }
    .subtitle { color: var(--muted); font-size: 14px; }

    .grid-frame {
      border: 1px solid var(--rule);
      border-radius: 10px;
      background: var(--panel);
      overflow: hidden;
      box-shadow: 0 16px 30px -22px rgba(15, 53, 86, 0.18);
    }
    .grid-frame-scroll { overflow-x: auto; }
    .grid-schedule {
      display: grid;
      min-width: 800px;
      font-size: 12px;
    }
    .gh {
      padding: 10px 6px;
      border-bottom: 1px solid var(--rule);
      border-right: 1px solid var(--rule-2);
      background: var(--panel-soft);
      color: var(--muted);
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      text-align: center;
      white-space: nowrap;
    }
    .gh.corner { text-align: left; padding-left: 14px; }
    .gh.weekend { background: #efe7d2; }

    .gname {
      padding: 12px 14px;
      border-bottom: 1px solid var(--rule-2);
      border-right: 1px solid var(--rule);
      background: #faf7ee;
      color: var(--ink);
      font-weight: 700;
      position: sticky;
      left: 0;
      z-index: 2;
    }
    .gcell {
      padding: 12px 4px;
      border-bottom: 1px solid var(--rule-2);
      border-right: 1px solid var(--rule-2);
      text-align: center;
      color: var(--muted);
      font-weight: 600;
    }
    .gcell.weekend { background: #fbf7ea; }
    .gcell.empty { color: #c8cfd6; }
"""
        + shift_css
        + """
    .grid-legend {
      display: flex;
      flex-wrap: wrap;
      gap: 20px;
      margin: 20px 0;
      color: var(--muted);
      font-size: 13px;
      font-weight: 600;
    }
    .lg { display: inline-flex; align-items: center; gap: 8px; }
    .swatch {
      width: 16px;
      height: 16px;
      border-radius: 4px;
      border: 1px solid var(--rule);
    }

    footer {
      margin-top: 40px;
      padding-top: 20px;
      border-top: 1px solid var(--rule);
      color: var(--muted);
      font-size: 12px;
      display: flex;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }
    .watermark a { color: var(--accent); text-decoration: none; font-weight: 700; }
    @media print {
      body { padding: 0; }
      .grid-frame { box-shadow: none; border-radius: 0; }
    }
    """
    )

    # Header row.
    header_html = '<div class="gh corner">Clinician</div>\n'
    for d in all_dates:
        weekend_cls = " weekend" if is_weekend(d) else ""
        header_html += f'<div class="gh{weekend_cls}">{d.strftime("%a %-d")}</div>\n'

    # Clinician rows.
    rows_html = ""
    for cid in clinician_ids:
        rows_html += f'<div class="gname">{clinicians[cid]["name"]}</div>\n'
        for d in all_dates:
            weekend_cls = " weekend" if is_weekend(d) else ""
            shifts = assignment_map.get((d, cid), [])
            is_vac = vacation_map.get((d, cid), False)

            if shifts:
                # If the same person is somehow on two shifts the same day,
                # show them stacked rather than dropping one silently.
                label = " / ".join(shifts)
                cls = shift_css_class(shifts[0])
                rows_html += (
                    f'<div class="gcell{weekend_cls} {cls}">{label}</div>\n'
                )
            elif is_vac:
                rows_html += f'<div class="gcell{weekend_cls} vac">VAC</div>\n'
            else:
                rows_html += f'<div class="gcell{weekend_cls} empty">&middot;</div>\n'

    # Legend — one entry per shift type actually used, then VAC.
    legend_items = ""
    for st in shift_types:
        cls = shift_css_class(st)
        legend_items += (
            f'<span class="lg"><span class="swatch {cls}"></span> {st} call</span>\n'
        )
    legend_items += (
        '<span class="lg"><span class="swatch vac"></span> Vacation / hard block</span>\n'
    )

    start_date_str = all_dates[0].strftime("%B %-d, %Y")
    end_date_str = all_dates[-1].strftime("%B %-d, %Y")

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
    <header>
      <h1>Call Schedule</h1>
      <div class="subtitle">{start_date_str} &ndash; {end_date_str}</div>
    </header>

    <div class="grid-frame">
      <div class="grid-frame-scroll">
        <div class="grid-schedule" style="grid-template-columns: 120px repeat({num_days}, minmax(60px, 1fr));">
          {header_html}
          {rows_html}
        </div>
      </div>
    </div>

    <div class="grid-legend">
      {legend_items}
    </div>

    <footer>
      <div>Generated on {date.today().strftime("%B %-d, %Y")}</div>
      <div class="watermark">Built with <a href="https://niceschedule.com">NiceSchedule.com</a></div>
    </footer>
  </div>
</body>
</html>
"""
    with output_path.open("w") as f:
        f.write(html)


def solve(config_path: Path) -> int:
    # The config file tells the solver where to find input CSVs, where to write
    # output, and how strongly to weight soft preferences.
    config = load_config(config_path)
    base_dir = config_path.parent.parent
    input_dir = base_dir / config["input_dir"]
    output_path = base_dir / config.get("output_csv", "output/schedule.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    clinicians = load_clinicians(input_dir / "clinicians.csv")
    coverage = load_coverage(input_dir / "coverage.csv")
    requests = load_requests(input_dir / "requests.csv")
    history_total, history_weekend = load_history(input_dir / "history.csv")

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
    # Honor hard requests, and try to honor soft requests.
    #
    # hard=1 in requests.csv means the assignment is blocked.
    # hard=0 means the solver may assign the clinician, but pays a penalty.
    objective_terms = []
    soft_request_weight = parse_int(str(weights.get("soft_request_violation", 25)))
    for request in requests:
        if request.clinician_id not in clinicians:
            raise ValueError(
                f"Request {request.request_id!r} references unknown clinician "
                f"{request.clinician_id!r}."
            )
        for cov_id, cov in enumerate(coverage):
            if not request_matches(request, cov.date, cov.shift_type):
                continue
            var = x[(cov_id, request.clinician_id)]
            if request.hard:
                model.Add(var == 0)
            else:
                objective_terms.append(soft_request_weight * var)

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

    # HARD RULE 5 and SOFT PREFERENCE 5:
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
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = Path(__file__).resolve().parent / config_path
    return solve(config_path)


if __name__ == "__main__":
    raise SystemExit(main())
