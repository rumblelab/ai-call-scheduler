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
| `hard` | Yes | `1` means the solver must honor it. `0` means avoid it if possible. |
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
