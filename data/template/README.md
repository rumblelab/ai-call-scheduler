# Data Template

Copy this folder to `data/my_data/`, then fill in your real roster, coverage, requests, and history.

```bash
cp -R data/template data/my_data
cp config/my_rules.template.json config/my_rules.json
```

`data/my_data/` and `config/my_rules.json` are ignored by Git so local schedule data does not get committed by accident.

In `clinicians.csv` you can leave `clinician_id` blank — it'll be derived from `name` (e.g. `Alice Smith` → `alice_smith`). In `requests.csv` and `history.csv` you can reference clinicians by id, slug, or the name itself; they all resolve to the same person. Fill in `clinician_id` explicitly only when two clinicians share a name.

Most groups generate `coverage.csv` instead of typing it by hand:

```bash
.venv/bin/python scripts/generate_coverage.py --year 2026 --month 7 --out data/my_data/coverage.csv
```

That reads `data/my_data/shift_pattern.csv` (included in this template) to decide which shifts run on which days. Edit `shift_pattern.csv` first — it is much shorter than `coverage.csv` — and the generator will fan it out across the month.

`shift_pattern.csv` has three columns:

| Column | Meaning |
| --- | --- |
| `shift_type` | `OR`, `OB`, `NIGHT`, ... |
| `weekday_mask` | 7 characters, Mon–Sun. `1` = include, `0` = skip. |
| `required_count` | How many clinicians needed for that day/shift. |

Common masks:

- `1111111` every day
- `1111100` weekdays only
- `0000011` weekends only
- `0000100` Fridays only

For different counts on weekdays vs weekends for the same shift, add two rows (e.g. `OR,1111100,2` and `OR,0000011,1`).
