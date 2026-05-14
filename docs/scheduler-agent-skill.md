# Scheduling Agent Skill

The skill of turning a human's scheduling rules into things the solver can act on. Read `AGENTS.md` first — it covers how to talk to the user, when to open the HTML, and the operating loop. This file is the deeper reference for *what the solver does* and *how to translate rules into it*.

## Prime directive

Do not ask a language model to invent the schedule directly. Use the language model to translate human rules into explicit data, constraints, and objective terms. The solver must produce the schedule.

## What the v1 solver does

The sample solver is intentionally small. It should:

1. Assign someone to every required shift in `coverage.csv`.
2. Avoid assigning clinicians on hard vacation or no-call requests.
3. Respect shift eligibility from `clinicians.csv`.
4. Assign each clinician to at most one shift per day.
5. Enforce minimum rest days between assignments.
6. Prefer fair total assignment counts.
7. Prefer fair weekend assignment counts.
8. Pull down whoever covered the most recent months (uses `history.csv`).
9. Prefer more spacing between assignments when the hard rules leave room.

It also writes a printable HTML version of the schedule next to the CSV output. Colors for any shift type (existing or new) are picked automatically from `SHIFT_PALETTE` in `solver.py`.

## Conversation pattern

When a user wants to adapt the solver, ask for rules in this order:

1. What shifts must be covered each day? (Drives `coverage.csv` via `scripts/generate_coverage.py`.)
2. Who is eligible for each shift type?
3. Which requests are hard blocks versus soft preferences?
4. What is the minimum rest rule?
5. What does fairness mean here: total shifts, weekends, holidays, call weights, or prior history?
6. What output format do they need?

## Rule translation examples

Human rule:

> Do not schedule someone while they are on vacation.

Solver translation:

> For each hard request row, set assignment variables to 0 for that clinician on every date in the request range. If `shift_type` is blank, block all shift types. If `shift_type` is present, block only that shift type.

Human rule:

> Everyone should get about the same number of calls.

Solver translation:

> Count assignments per clinician. Add absolute deviation variables from each clinician's target. Minimize the weighted sum of deviations.

Human rule:

> Avoid stacking people too close together if possible.

Solver translation:

> Keep the hard minimum rest constraint. Then add a soft penalty when assignments are closer than the preferred rest window.

## Guardrails

- Start with dummy data. Do not use real names or real schedules until the sample solver runs.
- Do not paste private physician schedules, vacation history, employment data, or patient information into public tools.
- Add one rule at a time. Run the solver after each change. Open the HTML after each run.
- If the model becomes infeasible, remove the newest rule first and inspect which coverage rows are hardest to fill. Tell the user in plain English ("the solver couldn't find a valid schedule — the OB shifts on the 4th and 5th had nobody eligible left"), not in solver-speak.
- Keep hard rules and soft preferences separate.

## Adapting the solver

Common rule additions (third shift type, locked assignments, weekend-pairing constraints, holiday balancing, post-call recovery, partner-vs-non-partner) are walked through in `docs/adaptation-cookbook.md`. Read it before suggesting any code change — the pattern of *change one thing, re-run, verify* applies to all of them.

When the solver errors, `docs/troubleshooting.md` has the exact text of every `ValueError` it can raise plus the fix.
