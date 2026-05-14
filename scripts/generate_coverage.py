#!/usr/bin/env python3
"""Generate a coverage.csv for a calendar month.

Helper for the NiceSchedule AI tutorial. The solver needs a coverage row for
every shift it has to staff; typing them by hand is tedious and error-prone.
This script writes a full month of rows using a simple repeating pattern.

The default pattern matches the sample data (one OR + one OB every day). Add
new shift types either by editing the SHIFT_PATTERN below, or by handing your
agent a description of the pattern you want and asking it to rewrite this file.

Examples:

    # Default: every day needs 1 OR and 1 OB.
    # Run after creating data/my_data from data/template.
    python scripts/generate_coverage.py --year 2026 --month 7

    # Custom path:
    python scripts/generate_coverage.py --year 2026 --month 7 \\
        --out data/my_data/coverage.csv
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path


# (shift_type, required_count, applies_on_weekend, applies_on_weekday)
#
# To add a third shift type (e.g. weekend-only BACKUP), append a row here and
# make sure clinicians.csv has a matching `can_backup` column.
# Otherwise the solver will refuse to run with:
#     Missing eligibility column 'can_backup' for shift type 'BACKUP'.
SHIFT_PATTERN: list[tuple[str, int, bool, bool]] = [
    ("OR", 1, True, True),
    ("OB", 1, True, True),
]


def generate_coverage(year: int, month: int, output_path: Path) -> int:
    start_date = date(year, month, 1)
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    end_date = next_month - timedelta(days=1)

    rows: list[dict[str, object]] = []
    current = start_date
    while current <= end_date:
        is_weekend = current.weekday() >= 5
        for shift_type, count, on_weekend, on_weekday in SHIFT_PATTERN:
            if is_weekend and not on_weekend:
                continue
            if not is_weekend and not on_weekday:
                continue
            rows.append(
                {
                    "date": current.isoformat(),
                    "shift_type": shift_type,
                    "required_count": count,
                }
            )
        current += timedelta(days=1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["date", "shift_type", "required_count"]
        )
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--year", type=int, required=True, help="Four-digit year, e.g. 2026.")
    parser.add_argument("--month", type=int, required=True, help="Month number 1-12.")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path. Defaults to data/my_data/coverage.csv.",
    )
    args = parser.parse_args()

    if not 1 <= args.month <= 12:
        parser.error("--month must be between 1 and 12.")

    repo_root = Path(__file__).resolve().parent.parent
    output_path = args.out
    if output_path is None:
        working_dir = repo_root / "data" / "my_data"
        if not working_dir.exists():
            parser.error(
                "data/my_data does not exist. Create it first with: "
                "cp -R data/template data/my_data"
            )
        output_path = working_dir / "coverage.csv"
    elif not output_path.is_absolute():
        output_path = repo_root / output_path

    count = generate_coverage(args.year, args.month, output_path)
    print(f"Wrote {count} coverage rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
