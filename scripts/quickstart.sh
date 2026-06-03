#!/usr/bin/env bash
# One-shot: set up the environment, solve the built-in sample, and open the
# result — so going from a fresh clone to a rendered schedule is a single
# command instead of four separate steps. Safe to re-run; the install is
# skipped when it's already in place.
set -euo pipefail
cd "$(dirname "$0")/.."

# 1. Virtual environment + dependencies. Both are skipped if already present,
#    so a second run goes straight to the solve.
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -c "import ortools" 2>/dev/null \
  || .venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt

# 2. Solve the built-in sample.
.venv/bin/python solver.py

# 3. Open the printable schedule (best-effort per OS).
case "$(uname -s)" in
  Darwin) open output/sample_schedule.html ;;
  Linux)  xdg-open output/sample_schedule.html >/dev/null 2>&1 || true ;;
  *)      echo "Done — open output/sample_schedule.html in your browser." ;;
esac
