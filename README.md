# AI Call Scheduler

A small, runnable example for anyone tempted to ask ChatGPT to invent a call schedule directly.

Do not do that. A language model can help translate your rules into code, but a deterministic constraint solver should be responsible for the schedule. This repo shows the smallest useful version of that pattern: structured CSVs in, [OR-Tools CP-SAT](https://developers.google.com/optimization/cp/cp_solver) in the middle, a printable HTML schedule out.

It was inspired by [a real r/Residency thread](https://www.reddit.com/r/Residency/comments/1r4zdjx/for_all_the_seniorchief_residents_how_do_you_make/) where the top reply said there is no replacement for doing it in Excel.

- Public walkthrough: <https://niceschedule.com/how-to-make-a-schedule-with-ai/>
- Solver: [`solver.py`](solver.py)
- Sample data: [`data/sample/`](data/sample/)

## Quick start

```bash
git clone https://github.com/rumblelab/ai-call-scheduler.git
cd ai-call-scheduler
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python solver.py
```

Expected output:

```text
Status: OPTIMAL
Wrote 28 assignments to output/sample_schedule.csv
```

Then open [`output/sample_schedule.html`](output/sample_schedule.html) in a browser to see the printable grid. That HTML view is the holy-shit moment — 28 assignments, every hard rule respected, six clinicians fairly distributed, ready to print.

## What v1 handles

Hard rules (the solver refuses to violate them):

1. Cover every required shift in `coverage.csv`.
2. Respect shift eligibility (`can_or`, `can_ob`, …).
3. Block hard vacation and no-call requests from `requests.csv`.
4. One assignment per clinician per day.
5. Minimum rest gap between assignments.
6. Per-clinician `max_shifts` and `max_weekend_shifts`.

Soft preferences (tunable in `config/sample_rules.json`):

- Land near each clinician's `target_shifts` and `target_weekend_shifts`.
- Balance total burden against prior `history.csv`.
- Honor soft (`hard=0`) requests when possible.
- Prefer more rest spacing beyond the hard minimum.

This is a teaching example, not a production scheduler. Real groups also need holiday rotation, partner-vs-non-partner allocation, post-call recovery, locked assignments, and local exceptions. The cookbook below shows how to add them one at a time.

## Docs

| File | When to read it |
| --- | --- |
| [`docs/csv-schema.md`](docs/csv-schema.md) | Every column in every input file, plus what each weight does. |
| [`docs/adaptation-cookbook.md`](docs/adaptation-cookbook.md) | Worked examples: third shift type, locked assignments, weekend pairing. |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | Every error the solver can raise and how to fix it. |
| [`docs/scheduler-agent-skill.md`](docs/scheduler-agent-skill.md) | Hand this to your coding agent before it edits anything. |
| [`docs/agent-privacy.md`](docs/agent-privacy.md) | What to do (and not do) with real physician data. |

## Hand it to your agent

Open the walkthrough above, scroll to "If you have Claude Code or Codex," and copy the prompt. It points your agent at the right files in the right order so it can run the dummy solve and start adapting it without flailing.

## Privacy

Start with synthetic data. Do not paste real physician names, vacation requests, schedules, patient information, employment data, hospital identifiers, or internal group rules into public AI tools or public GitHub issues. See [`docs/agent-privacy.md`](docs/agent-privacy.md).

## NiceSchedule

Maintained by RumbleLab, the team building [NiceSchedule](https://niceschedule.com/) for anesthesia groups. If you want a hosted version that tracks requests, schedule history, review, publishing, and distribution, that's what NiceSchedule is.

## License

MIT — see [LICENSE](LICENSE). Fork it, adapt it, ship it.
