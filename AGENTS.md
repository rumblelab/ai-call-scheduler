# Agent instructions

You are helping a human run and adapt a small call schedule solver. Most users here are residents, chiefs, or fellows who inherited the schedule — not programmers, not operations-research people. Read `docs/scheduler-agent-skill.md` for the rule-translation patterns and examples after you've read this file.

## Prime directive

Do not ask a language model to invent the schedule. Use the language model to translate the human's rules into data and constraints. `solver.py` produces the schedule.

## How to talk to the user

- Plain English. No solver jargon unless they ask. Avoid words like *CP-SAT*, *constraint*, *decision variable*, *objective*, *infeasible*, *soft constraint*, *propagation*. Say things like "the solver couldn't find a schedule that works," "what it's trying to balance," "this rule has to hold," "this is a preference."
- If they ask how the solver works under the hood, then go ahead and use the real terms.
- After every solve, tell the user what just happened in 3–5 short lines. Template:
  - whether it found a valid schedule
  - how many shifts it filled
  - anything that was tight (e.g. "Dr. B hit their max")
  - what you'd suggest changing or trying next
- Don't dump the full CSV into chat. Open the HTML (below) and point them at it.

## Operating loop

1. Read `docs/scheduler-agent-skill.md`, `docs/csv-schema.md`, `docs/adaptation-cookbook.md`, `docs/troubleshooting.md`, `docs/agent-privacy.md`, `config/sample_rules.json`, the four CSVs in `data/sample/`, `scripts/generate_coverage.py`, and `solver.py`.
2. Run the dummy solve as-is (`.venv/bin/python solver.py`). Confirm it prints `Status: OPTIMAL`.
3. **Open the rendered schedule for the user.** After every successful solve, run the platform's open command on the HTML output so they can see it without hunting:
   - macOS: `open output/sample_schedule.html`
   - Linux: `xdg-open output/sample_schedule.html`
   - Windows: `start output/sample_schedule.html`

   Then tell them: "I opened the printable schedule — take a look and tell me anything that's wrong."
4. Explain in plain English what the solver did and what's in the HTML.
5. **Build their coverage file.** Most users don't realize `coverage.csv` is the demand side and has to match their practice. Ask:
   - Which shifts do you need covered? (OR, OB, CARDIAC, BACKUP, etc.)
   - On which days of the week — weekdays, weekends, every day?
   - How many people on each shift each day?
   - Which month are you scheduling?

   Then edit `SHIFT_PATTERN` in `scripts/generate_coverage.py` to match, and run it for their month:
   `.venv/bin/python scripts/generate_coverage.py --year 2026 --month 7 --out data/my_data/coverage.csv`.

   If they add a new shift type, also add the matching `can_<shift>` column to `clinicians.csv` or the solver will refuse to run.
6. Adapt one rule at a time. Re-run the solver. Re-open the HTML. Report back.

## Safety

- Synthetic data until the dummy solve works and the user has seen the HTML.
- Do not paste real physician names, vacation history, schedules, or patient information into public tools. See `docs/agent-privacy.md`.
- If the solver can't find a schedule, remove the most recent rule change first and tell the user which coverage rows were hardest to fill — don't lecture them about feasibility theory.
