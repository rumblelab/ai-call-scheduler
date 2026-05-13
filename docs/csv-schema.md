# CSV Schema

The sample solver reads four CSV files from the configured input directory.

## `clinicians.csv`

| Column | Required | Meaning |
| --- | --- | --- |
| `clinician_id` | Yes | Stable ID used by other files. Prefer short IDs over full names. |
| `name` | Yes | Display name for output. |
| `active` | Yes | `1` if the clinician can be scheduled. |
| `fte` | No | Informational in v1. Useful for future target calculations. |
| `can_or` | Yes for `OR` shifts | `1` if eligible for OR. |
| `can_ob` | Yes for `OB` shifts | `1` if eligible for OB. |
| `target_shifts` | Yes | Preferred number of assignments in the solve period. |
| `max_shifts` | Yes | Hard maximum assignments in the solve period. |
| `target_weekend_shifts` | Yes | Preferred number of Saturday/Sunday assignments. |
| `max_weekend_shifts` | Yes | Hard maximum Saturday/Sunday assignments. |
| `min_days_between_assignments` | No | Hard rest spacing. If blank, the config default is used. |

For new shift types, add a column named `can_<shift_type_lowercase>`.
For example, `CARDIAC` uses `can_cardiac`.

## `coverage.csv`

| Column | Required | Meaning |
| --- | --- | --- |
| `date` | Yes | ISO date, `YYYY-MM-DD`. |
| `shift_type` | Yes | Shift to cover, such as `OR` or `OB`. |
| `required_count` | Yes | Number of clinicians needed for that date and shift type. |

## `requests.csv`

| Column | Required | Meaning |
| --- | --- | --- |
| `request_id` | Yes | Stable ID for the request. |
| `clinician_id` | Yes | Must match `clinicians.csv`. |
| `start_date` | Yes | ISO date, inclusive. |
| `end_date` | Yes | ISO date, inclusive. |
| `request_type` | Yes | Example: `vacation`, `no_call`, `prefer_off`. |
| `hard` | Yes | `1` means the solver must honor it. `0` means avoid it if possible. Blank defaults to `1` (hard block) — fill in `0` explicitly for soft requests. |
| `shift_type` | No | Blank means all shifts. Fill in to block or prefer off only for one shift type. |
| `note` | No | Human context. Not used by v1 solver. |

## `history.csv`

| Column | Required | Meaning |
| --- | --- | --- |
| `date` | Yes | ISO date. |
| `clinician_id` | Yes | Must match `clinicians.csv`. |
| `shift_type` | Yes | Historical shift type. |
| `status` | No | Example: `final`. Informational in v1. |

History is used only for fairness balancing in v1. It does not block assignments.

## `config/sample_rules.json`

The config file controls where data is read from, where output is written, and the relative weights of the soft objectives. The sample looks like this:

```json
{
  "input_dir": "data/sample",
  "output_csv": "output/sample_schedule.csv",
  "rules": {
    "min_days_between_assignments_default": 1,
    "preferred_days_between_assignments": 3,
    "weights": {
      "target_deviation": 100,
      "history_balance": 40,
      "weekend_deviation": 35,
      "soft_request_violation": 25,
      "rest_spacing": 5
    }
  }
}
```

### Top-level keys

| Key | Meaning |
| --- | --- |
| `input_dir` | Directory containing the four CSVs. Relative to the config file. |
| `output_csv` | Where the solved schedule is written. Relative to the config file. |

### `rules.min_days_between_assignments_default`

Hard floor on the rest gap between any clinician's two assignments. Used when `min_days_between_assignments` in `clinicians.csv` is blank for that clinician.

`1` means no two assignments on consecutive days. `2` means at least one full day off between assignments. `0` allows back-to-back.

### `rules.preferred_days_between_assignments`

The *preferred* rest gap — the solver pays a soft penalty when two assignments fall closer than this. The hard floor (above) is still enforced; this is the "ideal" spacing the solver tries to reach.

### `rules.weights`

These are the relative importances of the soft objectives. Higher number = the solver works harder to optimize that thing. They are unitless — only the *ratio* between them matters. Doubling all of them is a no-op.

| Weight | Default | What it controls |
| --- | --- | --- |
| `target_deviation` | 100 | Penalty per shift over or under each clinician's `target_shifts`. Highest weight in the sample — the solver tries hardest to hit targets. |
| `history_balance` | 40 | Penalty when (history + current) totals are imbalanced across clinicians. Pulls down whoever covered the most recent months. |
| `weekend_deviation` | 35 | Penalty per weekend shift over or under each clinician's `target_weekend_shifts`. Weekend fairness is tracked separately from total fairness. |
| `soft_request_violation` | 25 | Penalty when a `hard=0` request is violated. Set higher than `target_deviation` if you want soft requests to almost always be honored even at the cost of fairness. |
| `rest_spacing` | 5 | Small penalty whenever two assignments fall closer than `preferred_days_between_assignments`. The closer the pair, the higher the penalty. Low weight by design — the hard rest gap is what guarantees rest; this just gently spreads things out beyond the floor. |

### Tuning the weights

The shape of the schedule changes when these ratios change. A few common moves:

- **Targets feel ignored** → raise `target_deviation` to 150 or 200.
- **Weekend fairness keeps slipping** → raise `weekend_deviation` to match or exceed `target_deviation`.
- **Soft requests keep getting trampled** → raise `soft_request_violation` to 50 or above.
- **People keep getting double-booked tight even though rules say min 1 day** → raise `rest_spacing` to 20 or 30. Note: this is a soft preference; it cannot create rest the hard rules don't allow.

Always change one weight at a time. Solve. Look at the output. Compare to before. Tuning is iterative; there is no "correct" set of numbers — only the set that produces schedules your group accepts.
