# Scheduling Agent Skill

Use this when helping a human build or modify the sample call schedule solver.

## Prime Directive

Do not ask a language model to invent the schedule directly. Use the language model to translate human rules into explicit data, constraints, and objective terms. The solver must produce the schedule.

## What the v1 Solver Does

The sample solver is intentionally small. It should:

1. Assign someone to every required shift in `coverage.csv`.
2. Avoid assigning clinicians on hard vacation or no-call requests.
3. Respect shift eligibility from `clinicians.csv`.
4. Assign each clinician to at most one shift per day.
5. Enforce minimum rest days between assignments.
6. Prefer fair total assignment counts.
7. Prefer fair weekend assignment counts.
8. Prefer more spacing between assignments when the hard rules leave room.

## Conversation Pattern

When a user says they want to adapt the solver, ask for rules in this order:

1. What shifts must be covered each day?
2. Who is eligible for each shift type?
3. Which requests are hard blocks versus soft preferences?
4. What is the minimum rest rule?
5. What does fairness mean here: total shifts, weekends, holidays, call weights, or prior history?
6. What output format do they need?

## Rule Translation Examples

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
- Add one rule at a time. Run the solver after each change.
- If the model becomes infeasible, remove the newest rule first and inspect which coverage rows are hardest to fill.
- Keep hard rules and soft preferences separate.

## Good User Prompt

```text
I am using the sample call schedule solver from this folder.
Read docs/scheduler-agent-skill.md, config/sample_rules.json, and the CSV files in data/sample.
First help me run the dummy data exactly as-is.
After it works, help me adapt one rule at a time.
Do not use real names or real schedules until the dummy solve works.
```
