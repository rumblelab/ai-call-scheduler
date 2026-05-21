# AI Call Scheduler

Deterministic call schedules. Hand it a roster, the shifts to cover, and any time-off requests; it produces a printable HTML schedule that respects every hard rule and balances totals, weekends, and recent history.

The schedule itself is computed by [Google's OR-Tools](https://developers.google.com/optimization) — open-source, the same engine Google uses for its own logistics — so it doesn't hallucinate. AI is used only to translate human rules into the solver's input, never to invent the schedule. Inspired by [this r/Residency thread](https://www.reddit.com/r/Residency/comments/1r4zdjx/for_all_the_seniorchief_residents_how_do_you_make/) where the top reply said no AI could do it.

## I'm a chief, not a developer

You're in the wrong place. The walkthrough was written for you, on the web — no GitHub, no clone, no terminal:

**[niceschedule.com/how-to-make-a-schedule-with-ai](https://niceschedule.com/how-to-make-a-schedule-with-ai/)**

It walks you through pointing Claude Code or Codex at this repo and getting your first real schedule. If you want this done for you instead, **[NiceSchedule](https://niceschedule.com/)** is the hosted product — maintained by RumbleLab for anesthesia groups.

## I'm an agent

Read [`AGENTS.md`](AGENTS.md) before anything else. It covers your operating loop, how to talk to the chief, when to open the rendered HTML, what to edit and what to leave alone, and how to handle errors. The repo ships a `.claude/settings.json` that pre-allows the standard install and solve commands — that file only loads when your CWD is inside this folder, so if you cloned into a subdir, ask the user to reopen the session from inside `ai-call-scheduler/`.

## How it works

A small CP-SAT model in [`solver.py`](solver.py). Reads four CSVs in `data/sample/` — clinicians, coverage, requests, history — and writes an assignment list plus a printable HTML grid to `output/`.

Hard rules: cover every required shift, respect eligibility, honor hard time-off and locks, cap max shifts and weekend shifts, enforce minimum rest. Soft preferences: hit per-clinician shift and weekend targets, balance against recent history, spread weekday patterns over time, prefer more rest when feasible.

Reproducible per (year, month) seed. v1 supports `vacation`, `no_call`, `prefer_off`, and `lock` request types. Worked examples for adding holiday rotation, partner allocation, post-call recovery, and other group-specific rules live in [`docs/adaptation-cookbook.md`](docs/adaptation-cookbook.md).

| Doc | Purpose |
| --- | --- |
| [`docs/csv-schema.md`](docs/csv-schema.md) | Every column, every config weight. |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | Every error and how to fix it. |
| [`docs/adaptation-cookbook.md`](docs/adaptation-cookbook.md) | Worked examples for new rules. |
| [`docs/scheduler-agent-skill.md`](docs/scheduler-agent-skill.md) | Rule-translation patterns for agents. |
| [`docs/new-practice-setup.md`](docs/new-practice-setup.md) | First-time setup for a real group. |
| [`docs/agent-privacy.md`](docs/agent-privacy.md) | Brief privacy disclosure. |

## Privacy

The solver runs locally. Chat and coding-agent context may still be sent to your AI provider. Real display names are fine if that fits your workflow; use synthetic IDs for public examples or sensitive setups. Longer version in [`docs/agent-privacy.md`](docs/agent-privacy.md).

## License

MIT — see [LICENSE](LICENSE). Fork it, adapt it, ship it.
