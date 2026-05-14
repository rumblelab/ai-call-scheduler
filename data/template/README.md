# Data Template

Copy this folder to `data/my_data/`, then fill in your real roster, coverage, requests, and history.

```bash
cp -R data/template data/my_data
cp config/my_rules.template.json config/my_rules.json
```

`data/my_data/` and `config/my_rules.json` are ignored by Git so local schedule data does not get committed by accident.

Most groups generate `coverage.csv` instead of typing it by hand:

```bash
.venv/bin/python scripts/generate_coverage.py --year 2026 --month 7 --out data/my_data/coverage.csv
```
