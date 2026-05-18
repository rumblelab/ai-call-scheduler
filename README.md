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

Then say: *"Read AGENTS.md and help me run the sample solve."* Your agent does the rest.

### What your agent will do first

These are the commands the agent runs in the background to set the repo up — they're for the agent, not for you to type. The chief should see plain-English progress in chat, not shell blocks.

```bash
git clone https://github.com/rumblelab/ai-call-scheduler.git
cd ai-call-scheduler
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python solver.py
```

When the solve finishes, the agent should open [`output/sample_schedule.html`](output/sample_schedule.html) for you — the printable grid: 28 assignments, every hard rule respected, six clinicians fairly distributed, ready to print.

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
| [`docs/new-practice-setup.md`](docs/new-practice-setup.md) | Agent-facing walkthrough for the first real-practice schedule. |
| [`docs/agent-privacy.md`](docs/agent-privacy.md) | What to do (and not do) with real physician data. |

## Web chat instead of a coding agent

The setup above assumes Claude Code, Codex, Cursor, or another agent running in a cloned repo — they auto-load `AGENTS.md` and handle the rest. If you're in a web chat instead (ChatGPT.com, Claude.ai, no repo cloned), the [walkthrough](https://niceschedule.com/how-to-make-a-schedule-with-ai/) has a longer paste-in prompt that points the agent at this repo over the network.

## Set up your own schedule

After the sample solve looks right, tell your agent you're ready to build your own — something like *"Let's set up my real group's schedule."*

What the agent does for you:

- Copies the templates into `data/my_data/` and `config/my_rules.json` (local paths ignored by Git, so your roster never gets committed).
- Asks you about your group — who's on staff, what shifts run on which days, vacation and no-call requests, recent call history — and writes the answers into the CSVs.
- Runs the configured solve and opens the HTML output for you to review.

The commands the agent runs in the background (not for you to type):

```bash
cp -R data/template data/my_data
cp config/my_rules.template.json config/my_rules.json
.venv/bin/python scripts/run_my_schedule.py
```

## Use it again next month

Once your real `data/my_data/` plus `config/my_rules.json` are set up, you don't need to run the sample solve again. For each new month, just tell your agent *"start next month's schedule"* and pass on this month's vacation requests (paste a screenshot, an email thread, whatever you have).

What the agent does for you:

- Carries last month's output into `history.csv` so fairness stays balanced across months.
- Regenerates `coverage.csv` for the new month and updates the output filename in `config/my_rules.json`.
- Adds the new vacation and no-call requests to `requests.csv`.
- Updates `clinicians.csv` only if you mentioned roster, eligibility, target, or max changes.
- Runs the configured solve and opens the HTML for you to review.

The commands the agent runs in the background (not for you to type):

```bash
.venv/bin/python scripts/start_next_month.py
.venv/bin/python scripts/run_my_schedule.py
```

If you want a specific month instead of the next one inferred from the last output, tell the agent (e.g. *"start August 2026"*).

## Privacy

The solver runs locally, but chat and coding-agent context may still be sent to your AI provider. Use real display names if you're comfortable with that local workflow; use IDs or fake data for public examples, support requests, or sensitive schedules. See [`docs/agent-privacy.md`](docs/agent-privacy.md).

## NiceSchedule

Maintained by RumbleLab, the team building [NiceSchedule](https://niceschedule.com/) for anesthesia groups. If you want a hosted version that is tailored to your practice, that tracks requests, schedule history, review, publishing, distribution, and looks Nice, that's what NiceSchedule is.

## License

MIT — see [LICENSE](LICENSE). Fork it, adapt it, ship it.
