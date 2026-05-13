# Agent instructions

You are helping a human run and adapt a small constraint-solver call scheduler. Before editing anything, read `docs/scheduler-agent-skill.md` — it has the full file-reading order, conversation pattern, and guardrails.

## Prime directive

Do not ask a language model to invent the schedule. Use the LLM to translate human rules into data and constraints. The solver (`solver.py`, OR-Tools CP-SAT) produces the schedule.

## Order of operations

1. Read the files listed in `docs/scheduler-agent-skill.md`.
2. Run the dummy solve as-is (`python solver.py`) and confirm it prints `Status: OPTIMAL`.
3. Explain in plain English what the solver did.
4. Ask the user about their practice — coverage pattern, shift eligibility, hard vs soft requests, rest rules, what fairness means here — and use `scripts/generate_coverage.py` (edit `SHIFT_PATTERN` if a new shift type is needed) to build their `coverage.csv`.
5. Adapt one rule at a time. Re-run the solver after each change.

## Safety

- Use synthetic data until the dummy solve works.
- Do not paste real physician names, vacation history, schedules, or patient information into public tools. See `docs/agent-privacy.md`.
