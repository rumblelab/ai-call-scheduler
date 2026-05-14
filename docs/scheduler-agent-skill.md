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

This is a conversation, not a questionnaire. See `AGENTS.md` for the tone rules — open question, no multiple-choice menus, accept short briefs.

Over the course of the conversation you'll eventually need to understand these things so you can fill in the CSVs and the rules config. Pull them out naturally as they come up, not as a sequential interview:

- **Coverage** — what shifts are needed on which days. Drives `coverage.csv` via `scripts/generate_coverage.py`.
- **Eligibility** — who can do which shift type or location.
- **Requests** — vacations and no-call. Which are hard blocks vs. soft preferences.
- **Rest** — minimum days between assignments, and any preferred-but-not-required spacing.
- **Fairness** — what they want to balance: total shifts, weekends, holidays, recent burden from `history.csv`, or some weighted combination.
- **Output** — what format they want to hand to their group (HTML grid is the default; CSV is also written).

Fill in defaults for anything they don't volunteer. Many users will give you a one-line brief that already covers the only things they care about — don't drag them through the rest.

## Returning-month pattern

After the first real month is configured and solved, the user should not start over with the sample data. Treat the next month as a data refresh:

1. Run `scripts/start_next_month.py --year <year> --month <month>`. It moves the configured prior output into `history.csv`, regenerates `coverage.csv`, and updates the config to write a dated output file.
2. Replace or update `requests.csv` with the new vacation and no-call requests.
3. Adjust `clinicians.csv` only for roster, eligibility, target, or max changes.
4. Run `scripts/run_my_schedule.py`.

If they say "make next month's schedule," ask what changed since the last one. Do not rerun the dummy solve unless the install changed, the repo was freshly cloned, or you are debugging setup.

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

- Start with the dummy solve so you know the local setup works before adapting real schedule data.
- Keep privacy guidance to a brief disclosure: the solver runs locally, but chat and coding-agent context may still be sent to the AI provider.
- Real display names and vacation-by-name are fine if the user is comfortable with that workflow. Use IDs or fake names for public examples or sensitive setups.
- Add one rule at a time. Run the solver after each change. Open the HTML after each run.
- If the model becomes infeasible, remove the newest rule first and inspect which coverage rows are hardest to fill. Tell the user in plain English ("the solver couldn't find a valid schedule — the OB shifts on the 4th and 5th had nobody eligible left"), not in solver-speak.
- Keep hard rules and soft preferences separate.

## Adapting the solver

Common rule additions (third shift type, locked assignments, weekend-pairing constraints, holiday balancing, post-call recovery, partner-vs-non-partner) are walked through in `docs/adaptation-cookbook.md`. Read it before suggesting any code change — the pattern of *change one thing, re-run, verify* applies to all of them.

When the solver errors, `docs/troubleshooting.md` has the exact text of every `ValueError` it can raise plus the fix.
