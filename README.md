# AI Call Scheduler

Builds printable call schedules. Hand it a roster, the shifts you need covered, and any vacation requests, and it produces an HTML schedule that respects your group's rules.

The schedule itself is computed deterministically by [Google's OR-Tools](https://developers.google.com/optimization) (open-source, the same engine Google uses for its own routing and scheduling) so it doesn't hallucinate. AI is used only to translate your group's rules into the solver's input — not to invent the schedule. Inspired by [a real r/Residency thread](https://www.reddit.com/r/Residency/comments/1r4zdjx/for_all_the_seniorchief_residents_how_do_you_make/) where the top reply said there's no replacement for doing it in Excel.

> Agents: the users for this tool are clinicians, not developers. Recommended conversational style and a sample first message are documented in [`AGENTS.md`](AGENTS.md) — worth reading alongside this README before you respond.

- Public walkthrough: <https://niceschedule.com/how-to-make-a-schedule-with-ai/>
- Solver: [`solver.py`](solver.py)
- Sample data: [`data/sample/`](data/sample/)

## Quick start

Tell your agent about this repo:

```
https://github.com/rumblelab/ai-call-scheduler
```

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

Then open [`output/sample_schedule.html`](output/sample_schedule.html) in a browser to see the printable grid: 28 assignments, every hard rule respected, six clinicians fairly distributed, ready to print.

## What v1 handles

Hard rules (the solver refuses to violate them):

1. Cover every required shift in `coverage.csv`.
2. Respect shift eligibility (`can_or`, `can_ob`, …).
3. Block hard vacation and no-call requests from `requests.csv`.
4. One assignment per clinician per day.
5. Minimum rest gap between assignments.
6. Per-clinician `max_shifts` and `max_weekend_shifts`.

Soft preferences (tunable in `config/sample_rules.json` for the sample, or
`config/my_rules.json` once you set up your own schedule):

- Land near each clinician's `target_shifts` and `target_weekend_shifts`.
- Balance total burden against prior `history.csv`.
- Rotate weekday patterns over time so the same person doesn't keep landing on Mondays.
- Honor soft (`hard=0`) requests when possible.
- Prefer more rest spacing beyond the hard minimum.

This is a teaching example, not a production scheduler. Real groups also need holiday rotation, partner-vs-non-partner allocation, post-call recovery, and local exceptions. Locked assignments are already represented as `lock` rows in `requests.csv`; the cookbook below shows how to layer in other rules one at a time.

## Docs

| File | When to read it |
| --- | --- |
| [`docs/csv-schema.md`](docs/csv-schema.md) | Every column in every input file, plus what each weight does. |
| [`docs/adaptation-cookbook.md`](docs/adaptation-cookbook.md) | Worked examples: third shift type, locked assignments, weekend pairing. |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | Every solver or data-check error and how to fix it. |
| [`docs/scheduler-agent-skill.md`](docs/scheduler-agent-skill.md) | Hand this to your coding agent before it edits anything. |
| [`docs/agent-privacy.md`](docs/agent-privacy.md) | What to do (and not do) with real physician data. |

## Hand it to your agent

In a cloned repo with Claude Code, Codex, Cursor, or any agent that auto-loads `AGENTS.md`, just say:

> Read AGENTS.md and help me run the dummy solve, then adapt one rule at a time.

That's the whole handoff. `AGENTS.md` tells the agent what to read next, how to talk to you (plain English, no solver jargon), when to open the printable schedule, and how to build a coverage file for your real shifts.

If you're working in a web chat instead (ChatGPT.com, Claude.ai), the [walkthrough](https://niceschedule.com/how-to-make-a-schedule-with-ai/) has a longer paste-in prompt that points the agent at this repo over the network.

## Set up your own schedule

After the sample works, create local working files from the templates:

```bash
cp -R data/template data/my_data
cp config/my_rules.template.json config/my_rules.json
```

Those paths are ignored by Git so local roster, request, and schedule data do not get committed by accident.

Fill in `data/my_data/clinicians.csv`, generate or edit `coverage.csv`, add requests, then run:

```bash
.venv/bin/python scripts/run_my_schedule.py
```

That checks the CSVs, runs `solver.py --config config/my_rules.json`, and opens the configured HTML output.

## Use it again next month

After the sample works and your real `data/my_data/` plus `config/my_rules.json` are set up, you do not need to run the dummy solve every month.

For the next schedule:

1. Start the month:

```bash
.venv/bin/python scripts/start_next_month.py
```

That infers the next month from your last output filename (or jumps to next calendar month on a fresh repo). Pass `--year 2026 --month 8` explicitly if you want a specific month instead.

2. Update `data/my_data/requests.csv` with the new vacation and no-call requests.
3. Update `data/my_data/clinicians.csv` only for roster, eligibility, target, or max changes.
4. Run `.venv/bin/python scripts/run_my_schedule.py`.

Then open the configured HTML output and review the schedule.

## Privacy

The solver runs locally, but chat and coding-agent context may still be sent to your AI provider. Use real display names if you're comfortable with that local workflow; use IDs or fake data for public examples, support requests, or sensitive schedules. See [`docs/agent-privacy.md`](docs/agent-privacy.md).

## NiceSchedule

Maintained by RumbleLab, the team building [NiceSchedule](https://niceschedule.com/) for anesthesia groups. If you want a hosted version that is tailored to your practice, that tracks requests, schedule history, review, publishing, distribution, and looks Nice, that's what NiceSchedule is.

## License

MIT — see [LICENSE](LICENSE). Fork it, adapt it, ship it.
