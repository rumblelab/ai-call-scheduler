# Adaptation Cookbook

Three worked examples of changes a real group will want, in order of difficulty. Each one shows:

1. What rows/columns to change in the CSVs.
2. What (if anything) to change in `solver.py`.
3. How to test it.

These are designed so an agent can read this file, pattern-match, and implement the change with you. Always run the dummy solve before each change, then re-run after, and compare the output.

The pattern beneath all three: **change one thing, re-run, verify.** Do not stack changes.

---

## 1. Add a third shift type (e.g. NIGHT)

The solver already handles arbitrary shift types — no code changes needed. You just need to update two CSVs.

### CSV changes

**`coverage.csv`** — add rows for the new shift on the dates it's needed:

```csv
date,shift_type,required_count
2026-06-01,NIGHT,1
2026-06-02,NIGHT,1
2026-06-03,NIGHT,1
...
```

**`clinicians.csv`** — add a new column `can_night`. Put `1` next to every clinician eligible for NIGHT, `0` for the rest:

```csv
clinician_id,name,active,fte,can_or,can_ob,can_night,target_shifts,max_shifts,target_weekend_shifts,max_weekend_shifts,min_days_between_assignments
cary,M. Cary,1,1.0,1,1,1,5,6,2,3,1
fox,A. Fox,1,1.0,1,1,0,5,6,2,3,1
...
```

### Code changes

None. The solver discovers shift types from `coverage.csv` and resolves the matching `can_<shift>` column automatically — see the block that builds `shift_types` and verifies eligibility columns near the top of `solve()` in `solver.py`. The HTML renderer also picks a stable color for the new shift type automatically (see `SHIFT_PALETTE` and `shift_colors` near the top of `solver.py`).

### How to test

```bash
.venv/bin/python solver.py
```

You should see `Status: OPTIMAL` and roughly `28 + N` assignments where `N` is the number of new NIGHT coverage rows. Open `output/sample_schedule.csv` and confirm:

- NIGHT shifts are filled.
- Only clinicians with `can_night=1` got NIGHT shifts.
- Total assignments per clinician are still balanced.

If you get `Missing eligibility column 'can_night' for shift type 'NIGHT'.` — you forgot the column. Add it.

If you get `No feasible schedule found.` — too few clinicians have `can_night=1` to cover the new demand, or it conflicts with `max_shifts`. Either raise `max_shifts`, add more eligible clinicians, or reduce NIGHT `required_count`.

---

## 2. Add locked assignments (pin a person to a specific shift)

Sometimes you want to lock in: "Cary takes Friday June 5 OR no matter what." Maybe Cary asked for it, maybe it's a teaching obligation, maybe it's already published.

### CSV changes

Create a new file `data/sample/locked_assignments.csv`:

```csv
date,shift_type,clinician_id
2026-06-05,OR,cary
2026-06-12,OB,fox
```

### Code changes

Add a small block to `solver.py`. The natural place is **after the `# HARD RULE 2` (eligibility) block and before the `coverage_by_date` / `day_assigned` setup** — search for those identifiers in the file. Roughly:

```python
# HARD RULE: locked assignments.
# If a row exists in locked_assignments.csv, pin that clinician to that
# exact shift on that exact date.
locked_path = input_dir / "locked_assignments.csv"
if locked_path.exists():
    with locked_path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            target_date = date.fromisoformat(row["date"])
            target_shift = row["shift_type"].strip().upper()
            target_clinician = row["clinician_id"].strip()
            if target_clinician not in clinicians:
                raise ValueError(
                    f"Locked assignment references unknown clinician {target_clinician!r}"
                )
            for cov_id, cov in enumerate(coverage):
                if cov.date == target_date and cov.shift_type == target_shift:
                    model.Add(x[(cov_id, target_clinician)] == 1)
```

The agent prompt should be: *"Add a hard constraint that pins clinicians from `data/sample/locked_assignments.csv` to the exact (date, shift_type) row. Read it like the existing CSV readers in solver.py."*

### How to test

Re-run the solver and check `output/sample_schedule.csv`:

- The locked rows must appear exactly as specified.
- Total counts may shift slightly (the locked person now has one assignment "spent" in a specific slot).
- If you locked something the rules forbid (e.g. on a vacation date, or for a clinician who has `can_or=0`), the model becomes infeasible.

If infeasible: remove the locked row that contradicts a hard rule. The error doesn't pinpoint which one — bisect by commenting out half the locked rows and re-solving.

---

## 3. Add a weekend-pairing rule (no Sat + Sun back to back)

"Don't make anyone work both Saturday and Sunday of the same weekend" is a fairness rule almost every group has. The dummy solver doesn't enforce it; the OPTIMAL output happens to spread it out, but for a tighter month the solver will sometimes stack both weekend days on one person.

### CSV changes

None. This is a pure code rule.

### Code changes

In `solver.py`, after the existing weekend objective block (search for `weekend_count` and the `SOFT PREFERENCE` for weekend deviation), add a hard constraint:

```python
# HARD RULE: no clinician works both Saturday and Sunday of the same weekend.
for clinician_id in clinician_ids:
    for day in all_dates:
        if day.weekday() != 5:  # 5 = Saturday
            continue
        sunday = day + timedelta(days=1)
        sat_var = day_assigned.get((day, clinician_id))
        sun_var = day_assigned.get((sunday, clinician_id))
        if sat_var is not None and sun_var is not None:
            model.Add(sat_var + sun_var <= 1)
```

`timedelta` is already imported at the top of `solver.py` — you don't need to re-import it.

This says: for every (Saturday, Sunday) pair in the solve window, no clinician can be on both. Note this uses `day_assigned`, which is the per-day "does this clinician work today" boolean already built by the solver.

The agent prompt: *"Add a hard rule that no clinician is assigned to both Saturday and Sunday of the same weekend. Use the existing day_assigned variables. Apply across all weekends in the solve window."*

### Soft version

If you want this as a preference instead of a hard rule, swap `model.Add(sat_var + sun_var <= 1)` for an objective penalty:

```python
both_weekend = model.NewBoolVar(f"both_we_{clinician_id}_{day}")
model.AddBoolAnd([sat_var, sun_var]).OnlyEnforceIf(both_weekend)
model.AddBoolOr([sat_var.Not(), sun_var.Not()]).OnlyEnforceIf(both_weekend.Not())
objective_terms.append(50 * both_weekend)  # weight = 50, tune as needed
```

### How to test

Re-run, open `output/sample_schedule.csv`, and check: no clinician should have an assignment on both June 6 (Sat) and June 7 (Sun), or June 13 (Sat) and June 14 (Sun).

If you can't find a feasible schedule, your group may not have enough weekend-eligible coverage to support the rule. Either soften it, raise `max_weekend_shifts`, or accept that some pairings have to happen during heavy months.

---

## What to add next

The pattern is the same for almost any rule:

- **Holiday balancing:** add a `holidays.csv` (date list), count assignments on those dates per clinician, add an objective term that minimizes the spread.
- **Post-call recovery:** after a NIGHT shift, no shift the next day. This is a rest-gap rule specific to one shift type — extend the existing `min_days_between_assignments` logic to be per-shift-type.
- **Partner vs non-partner:** add an `is_partner` column to `clinicians.csv`, then add an objective that pushes leftover call onto partners after non-partners hit their `target_shifts`.
- **Site-specific eligibility:** already supported. Just use distinct shift types (`NORTH`, `SOUTH`, `EAST`) and matching `can_*` columns.

For each one, the agent prompt is: *"Read solver.py, then add `<rule>`. Add it as a hard constraint by default. Tell me what to change in the CSVs and how to test it. Run the dummy solve after."*

Add one rule at a time. Always re-run the dummy solve. Compare outputs before and after.
