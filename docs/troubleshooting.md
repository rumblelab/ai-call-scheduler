# Troubleshooting

What to do when the solver complains. Every error below is one the v1 solver actually raises — they are quoted from `solver.py` so an agent can grep for them.

The general rule when something breaks: **remove the most recent change first.** Most failures here are introduced by edits to the CSVs, not by the solver itself.

---

## Setup errors

### `ModuleNotFoundError: No module named 'ortools'`

You skipped the install, or you're running the system Python instead of the venv one.

Fix:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python solver.py
```

On Windows the venv path is different — use `.venv\Scripts\python` wherever this guide shows `.venv/bin/python`.

### OR-Tools install hangs or fails

`ortools` is a compiled package. On a slow connection or an older machine, install can take 30–60 seconds with no progress output. That's normal; let it finish.

If it actually errors, the usual culprits are:

- Python older than 3.9 — check with `python3 --version`. OR-Tools 9.x needs 3.9+.
- An x86-only Python on Apple Silicon. Reinstall a native arm64 Python.
- Corporate network blocking PyPI. Use a personal network or have your agent install through a mirror.

---

## CSV / data errors

These all raise as `ValueError` and stop the solver before it tries to solve.

### `Missing clinician_id in <path>`

A row in `clinicians.csv` has an empty `clinician_id` column. Open the file and check for trailing blank rows or a row where the first column is missing.

### `Duplicate clinician_id 'X'`

Two rows in `clinicians.csv` use the same `clinician_id`. IDs must be unique. Note that `clinician_id` is the stable key — change the name if you need to, but don't reuse an ID.

### `No active clinicians found.`

Every row in `clinicians.csv` has `active=0`, or the file is empty. Set `active=1` on at least the clinicians you want included in this solve.

### `No coverage rows found.`

`coverage.csv` is empty (or only has a header). The solver has nothing to schedule. Generate coverage rows for the dates and shift types you want filled. See the [coverage section of the walkthrough](https://niceschedule.com/how-to-make-a-schedule-with-ai/#coverage) for the script pattern.

### `Missing eligibility column 'can_X' for shift type 'X'.`

You added a new shift type to `coverage.csv` but didn't add the matching eligibility column to `clinicians.csv`. The rule is one-to-one:

- shift type `OR` → column `can_or`
- shift type `OB` → column `can_ob`
- shift type `NIGHT` → column `can_night`
- shift type `CARDIAC` → column `can_cardiac`

Open `clinicians.csv`, add a `can_<shift_lowercase>` column, and put `1` next to every clinician who can cover it.

### `Request 'X' references unknown clinician 'Y'.`

A row in `requests.csv` has a `clinician_id` that doesn't exist in `clinicians.csv` (or that clinician has `active=0`). Either typo, or the clinician was renamed/removed and the request wasn't updated. Fix the ID or delete the request row.

### `history.csv references unknown clinician 'Y'.`

Same idea: a row in `history.csv` points to a `clinician_id` that isn't in `clinicians.csv`, or to one whose `active` is `0`. Update the ID, mark the clinician active, or drop the history row.

---

## Solver errors

### `No feasible schedule found. Try relaxing max_shifts, max_weekend_shifts, rest gaps, or hard requests.`

The solver tried, and there is no way to satisfy every hard rule simultaneously. The error message lists the four most common culprits in rough order. Walk them in this order:

1. **Did you just add a new hard rule or a new hard request?** Comment that change out and re-solve. If it works without that rule, the conflict is there — relax it or make it soft (set `hard=0` in `requests.csv`).
2. **Does total demand exceed total capacity?** Sum the `required_count` column in `coverage.csv` for the solve window. Compare to the sum of `max_shifts` across all active clinicians. If demand > max capacity, the model can't possibly cover. Lower `required_count` somewhere or raise `max_shifts`.
3. **Are weekend caps too tight?** Count weekend coverage rows (Sat + Sun within the solve window). Sum `max_weekend_shifts` across clinicians. If demand exceeds cap, you'll be infeasible.
4. **Did you set a long `min_days_between_assignments`?** A 3+ day rest gap with daily coverage is hard to satisfy with a small group. Try lowering the gap.
5. **Is anyone's eligibility wrong?** If `can_or` is set to 0 for everyone who can actually cover OR, the solver has no eligible candidates.

The fastest debugging move is: temporarily delete `requests.csv` (or move it aside), re-solve. If that succeeds, you know it's a request that's blocking. Then add requests back one at a time.

### Status: `FEASIBLE` (instead of `OPTIMAL`)

The solver hit its 60-second time limit before proving optimality. The schedule is still valid — every hard rule was respected — it just may not be the *most* fair option. For dummy data this should never happen; for larger real-world inputs, you can either:

- Accept it (the schedule is correct, just possibly slightly imbalanced)
- Raise the time limit in `solver.py` (search for the `cp_model.CpSolver()` block and look for the time-limit field)
- Reduce the size of the solve window (one month at a time, not three)

---

## Behavior surprises (not errors, but "wait why")

### Someone got fewer shifts than their `target_shifts`

`target_shifts` is a soft preference, not a guarantee. The solver will trade off targets against weekend fairness, rest spacing, and request honoring. If a clinician has tight `max_weekend_shifts` and a bunch of vacation, they'll naturally come in under target. Increase `target_deviation` in the weights (see `docs/csv-schema.md`) to push targets harder.

### A soft request was ignored

Soft requests pay a penalty (`soft_request_violation`, default 25) but don't block. If another objective term outweighs the penalty (e.g. honoring it would force a much larger fairness imbalance), the solver will violate the request. Raise `soft_request_violation` in the weights, or make the request hard.

### Vacations on weekdays only — weekends fine?

Check the `shift_type` column in `requests.csv`. If it's blank, the request blocks *all* shifts on those dates. If it has a value (e.g. `OB`), it only blocks that shift type — other shifts on the same date are still fair game.

### History.csv seems ignored

History is used for the `history_balance` weight only. It doesn't block; it tries to give people who carried more burden recently a lighter load now. If you want history to *block* (e.g. "Fox covered the last 3 weekends, do not assign Fox this weekend"), encode that as a hard request, not a history row.

---

## When to ask for help

If you've worked through this list and the solver still won't solve, paste the full error message and the relevant CSV row(s) into your coding agent and ask it to walk the model with you. If the agent is stuck too, email `moultrie@niceschedule.com` with the CSVs and the error output.
