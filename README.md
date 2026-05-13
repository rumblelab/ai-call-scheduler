# AI Call Scheduler

Use AI to help write scheduling constraints. Use OR-Tools CP-SAT to solve the schedule.

This repo is a small, runnable example for people who are tempted to ask ChatGPT to make a call schedule directly. Do not do that. A language model can help translate your rules into code, but a deterministic solver should be responsible for the schedule.

Start here:

- Public walkthrough: https://niceschedule.com/how-to-make-a-schedule-with-ai/
- Solver script: `solver.py`
- Sample data: `data/sample/`
- Agent handoff: `docs/scheduler-agent-skill.md`

## Quick Start

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python solver.py
```

Expected result:

```text
Status: OPTIMAL
Wrote 28 assignments to output/sample_schedule.csv
```

## What This Handles

- required shift coverage
- clinician eligibility
- hard vacation and no-call requests
- one assignment per clinician per day
- minimum rest gaps
- fair total assignment counts
- fair weekend assignment counts
- simple history-aware fairness

This is a teaching example, not a production scheduling system.

## Privacy

Use synthetic data first. Do not upload real physician names, vacation requests, schedules, patient information, private employment data, hospital identifiers, or internal group rules to public GitHub issues.

## NiceSchedule

This repo is maintained by RumbleLab, the team building NiceSchedule for anesthesia groups.

If you want a hosted version that tracks requests, schedule history, review, publishing, and distribution, see:

https://niceschedule.com/
