#!/usr/bin/env python3
"""Check configured schedule data before running the solver."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


REQUIRED_FIELDS = {
    "clinicians.csv": [
        "clinician_id",
        "name",
        "active",
        "target_shifts",
        "max_shifts",
        "target_weekend_shifts",
        "max_weekend_shifts",
    ],
    "coverage.csv": ["date", "shift_type", "required_count"],
    "requests.csv": [
        "request_id",
        "clinician_id",
        "start_date",
        "end_date",
        "request_type",
        "hard",
        "shift_type",
        "note",
    ],
    "history.csv": ["date", "clinician_id", "shift_type", "status"],
}


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or [], list(reader)


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def parse_date(value: str) -> bool:
    try:
        datetime.strptime(value.strip(), "%Y-%m-%d")
    except ValueError:
        return False
    return True


def eligibility_column(shift_type: str) -> str:
    return "can_" + shift_type.lower().replace(" ", "_").replace("-", "_")


def main() -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="config/my_rules.json",
        help="Configured rules file. Defaults to config/my_rules.json.",
    )
    args = parser.parse_args()

    config_path = resolve_path(root, args.config)
    errors: list[str] = []
    warnings: list[str] = []

    if not config_path.exists():
        errors.append(f"Missing config file: {config_path}")
        errors.append("Create it with: cp config/my_rules.template.json config/my_rules.json")
        return report(errors, warnings)

    with config_path.open() as f:
        config = json.load(f)

    base_dir = config_path.parent.parent
    input_dir = resolve_path(base_dir, config["input_dir"])
    if not input_dir.exists():
        errors.append(f"Missing input directory: {input_dir}")
        errors.append("Create it with: cp -R data/template data/my_data")
        return report(errors, warnings)

    csv_data: dict[str, tuple[list[str], list[dict[str, str]]]] = {}
    for filename, required in REQUIRED_FIELDS.items():
        path = input_dir / filename
        fields, rows = read_csv(path)
        csv_data[filename] = (fields, rows)
        if not path.exists():
            errors.append(f"Missing {path}")
            continue
        missing = [field for field in required if field not in fields]
        if missing:
            errors.append(f"{filename} is missing columns: {', '.join(missing)}")

    clinician_fields, clinician_rows = csv_data.get("clinicians.csv", ([], []))
    coverage_fields, coverage_rows = csv_data.get("coverage.csv", ([], []))
    _request_fields, request_rows = csv_data.get("requests.csv", ([], []))
    _history_fields, history_rows = csv_data.get("history.csv", ([], []))

    active_ids: set[str] = set()
    seen_ids: set[str] = set()
    total_capacity = 0
    weekend_capacity = 0
    for index, row in enumerate(clinician_rows, start=2):
        clinician_id = row.get("clinician_id", "").strip()
        if not clinician_id:
            errors.append(f"clinicians.csv row {index} has a blank clinician_id")
            continue
        if clinician_id in seen_ids:
            errors.append(f"clinicians.csv has duplicate clinician_id {clinician_id!r}")
        seen_ids.add(clinician_id)
        if parse_bool(row.get("active", "1")):
            active_ids.add(clinician_id)
            total_capacity += parse_nonnegative_int(
                row.get("max_shifts", ""), f"clinicians.csv row {index} max_shifts", errors
            )
            weekend_capacity += parse_nonnegative_int(
                row.get("max_weekend_shifts", ""),
                f"clinicians.csv row {index} max_weekend_shifts",
                errors,
            )

    if clinician_rows and not active_ids:
        errors.append("No active clinicians found in clinicians.csv")

    shift_types: set[str] = set()
    total_demand = 0
    weekend_demand = 0
    for index, row in enumerate(coverage_rows, start=2):
        raw_date = row.get("date", "")
        if not parse_date(raw_date):
            errors.append(f"coverage.csv row {index} has an invalid date {raw_date!r}")
        shift_type = row.get("shift_type", "").strip().upper()
        if not shift_type:
            errors.append(f"coverage.csv row {index} has a blank shift_type")
            continue
        shift_types.add(shift_type)
        count = parse_positive_int(
            row.get("required_count", ""), f"coverage.csv row {index} required_count", errors
        )
        total_demand += count
        if parse_date(raw_date) and datetime.strptime(raw_date.strip(), "%Y-%m-%d").weekday() >= 5:
            weekend_demand += count

    if not coverage_rows:
        errors.append("coverage.csv has no rows")

    for shift_type in sorted(shift_types):
        column = eligibility_column(shift_type)
        if column not in clinician_fields:
            errors.append(f"Missing eligibility column {column!r} for shift type {shift_type!r}")
            continue
        eligible = [
            row.get("clinician_id", "").strip()
            for row in clinician_rows
            if row.get("clinician_id", "").strip() in active_ids
            and parse_bool(row.get(column, "0"))
        ]
        if not eligible:
            errors.append(f"No active clinicians are eligible for {shift_type}")

    check_reference_rows("requests.csv", request_rows, active_ids, errors)
    check_reference_rows("history.csv", history_rows, active_ids, errors)

    if total_demand > total_capacity:
        warnings.append(
            f"Total demand ({total_demand}) exceeds total max_shifts ({total_capacity})."
        )
    if weekend_demand > weekend_capacity:
        warnings.append(
            f"Weekend demand ({weekend_demand}) exceeds total max_weekend_shifts ({weekend_capacity})."
        )

    return report(errors, warnings)


def check_reference_rows(
    filename: str,
    rows: list[dict[str, str]],
    active_ids: set[str],
    errors: list[str],
) -> None:
    date_fields = ["date"] if filename == "history.csv" else ["start_date", "end_date"]
    for index, row in enumerate(rows, start=2):
        clinician_id = row.get("clinician_id", "").strip()
        if clinician_id and clinician_id not in active_ids:
            errors.append(f"{filename} row {index} references unknown clinician {clinician_id!r}")
        for field in date_fields:
            value = row.get(field, "")
            if value and not parse_date(value):
                errors.append(f"{filename} row {index} has an invalid {field} {value!r}")


def parse_nonnegative_int(value: str, label: str, errors: list[str]) -> int:
    value = value.strip()
    if not value:
        return 0
    try:
        parsed = int(value)
    except ValueError:
        errors.append(f"{label} must be a number")
        return 0
    if parsed < 0:
        errors.append(f"{label} cannot be negative")
        return 0
    return parsed


def parse_positive_int(value: str, label: str, errors: list[str]) -> int:
    parsed = parse_nonnegative_int(value, label, errors)
    if parsed == 0:
        errors.append(f"{label} must be at least 1")
    return parsed


def report(errors: list[str], warnings: list[str]) -> int:
    if errors:
        print("Data check found problems:")
        for error in errors:
            print(f"  - {error}")
    if warnings:
        print("Data check warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    if errors:
        return 2
    print("Data check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
