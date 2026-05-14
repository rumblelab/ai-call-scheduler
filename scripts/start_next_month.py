#!/usr/bin/env python3
"""Prepare the configured data folder for the next schedule month."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_coverage import generate_coverage  # noqa: E402


HISTORY_FIELDS = ["date", "clinician_id", "shift_type", "status"]
REQUEST_FIELDS = [
    "request_id",
    "clinician_id",
    "start_date",
    "end_date",
    "request_type",
    "hard",
    "shift_type",
    "note",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def read_existing_history(path: Path) -> set[tuple[str, str, str]]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8-sig") as f:
        return {
            (
                row.get("date", "").strip(),
                row.get("clinician_id", "").strip(),
                row.get("shift_type", "").strip(),
            )
            for row in csv.DictReader(f)
        }


def append_output_to_history(prior_output: Path, history_path: Path) -> int:
    if not prior_output.exists():
        print(f"No prior output found at {prior_output}; skipped history update.")
        return 0

    existing = read_existing_history(history_path)
    rows_to_append: list[dict[str, str]] = []
    with prior_output.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = (
                row["date"].strip(),
                row["clinician_id"].strip(),
                row["shift_type"].strip(),
            )
            if key in existing:
                continue
            existing.add(key)
            rows_to_append.append(
                {
                    "date": key[0],
                    "clinician_id": key[1],
                    "shift_type": key[2],
                    "status": "final",
                }
            )

    if not rows_to_append:
        print("History already contains the prior output rows.")
        return 0

    history_path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not history_path.exists() or history_path.stat().st_size == 0
    with history_path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if needs_header:
            writer.writeheader()
        writer.writerows(rows_to_append)
    return len(rows_to_append)


def reset_requests(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REQUEST_FIELDS)
        writer.writeheader()


def main() -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True, help="Four-digit year, e.g. 2026.")
    parser.add_argument("--month", type=int, required=True, help="Month number 1-12.")
    parser.add_argument(
        "--config",
        default="config/my_rules.json",
        help="Configured rules file. Defaults to config/my_rules.json.",
    )
    parser.add_argument(
        "--prior-output",
        default=None,
        help="Prior schedule CSV to append to history. Defaults to current output_csv.",
    )
    parser.add_argument(
        "--output-csv",
        default=None,
        help="Next output CSV. Defaults to output/YYYY-MM_schedule.csv.",
    )
    parser.add_argument(
        "--reset-requests",
        action="store_true",
        help="Replace requests.csv with just the header row for the new month.",
    )
    args = parser.parse_args()

    if not 1 <= args.month <= 12:
        parser.error("--month must be between 1 and 12.")

    config_path = resolve_path(root, args.config)
    if not config_path.exists():
        print(f"Missing {display_path(root, config_path)}.")
        print("Create it first:")
        print("  cp -R data/template data/my_data")
        print("  cp config/my_rules.template.json config/my_rules.json")
        return 2

    with config_path.open() as f:
        config = json.load(f)

    base_dir = config_path.parent.parent
    input_dir = resolve_path(base_dir, config["input_dir"])
    if not input_dir.exists():
        print(f"Missing input directory: {input_dir}")
        print("Create it first: cp -R data/template data/my_data")
        return 2

    prior_output_value = args.prior_output or config.get("output_csv", "output/schedule.csv")
    prior_output = resolve_path(base_dir, prior_output_value)
    history_path = input_dir / "history.csv"
    coverage_path = input_dir / "coverage.csv"
    requests_path = input_dir / "requests.csv"

    history_count = append_output_to_history(prior_output, history_path)
    coverage_count = generate_coverage(args.year, args.month, coverage_path)

    if args.reset_requests:
        reset_requests(requests_path)
        requests_message = "Reset requests.csv to a blank header."
    else:
        requests_message = "Left requests.csv in place; update it for the new month."

    next_output = args.output_csv or f"output/{args.year}-{args.month:02d}_schedule.csv"
    config["output_csv"] = next_output
    with config_path.open("w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    print(f"Added {history_count} prior assignments to {history_path}.")
    print(f"Wrote {coverage_count} coverage rows to {coverage_path}.")
    print(requests_message)
    print(f"Updated {config_path} to write {next_output}.")
    print()
    print("Next run:")
    print("  .venv/bin/python scripts/run_my_schedule.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
