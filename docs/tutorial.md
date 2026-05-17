# How to make a simple call schedule solver using AI that does not hallucinate

Author: Moultrie Ball  
Read time: 30 minutes  
Time to first dummy schedule: 10 minutes  
Time to first custom schedule: about 1 hour

Most people using ChatGPT for scheduling are asking the wrong question.

If you ask a language model to make your call schedule directly, it can produce something that looks reasonable while quietly breaking your rules. That is not a scheduling system. That is a plausible-looking guess.

The better pattern is:

1. Use AI to help translate your rules into code.
2. Use a deterministic solver to generate the schedule.
3. Validate the output before anyone relies on it.

This tutorial shows the smallest useful version of that pattern. We will use a Python constraint solver called OR-Tools CP-SAT. You will start with dummy data, prove the solver works, then replace the dummy files with your own data one file at a time.

If this gets tricky, use a coding agent. Point Codex, Claude Code, ChatGPT, or your preferred agent at this page and the files in this folder. Tell it to help you run the dummy solve first. Do not start with real physician names or real vacation data.

This is free on purpose. If you are a resident, chief resident, fellow, or unlucky person who inherited the call schedule, I want you to be able to run this without buying anything.

If you want a simple hosted web version of this free tool, email me and I will tell you if we build it. If you are a real anesthesia group that wants the secure, maintained version with requests, history, permissions, review, and distribution, that is where NiceSchedule comes in.

> If setup breaks, hand this whole block to your coding agent:
>
> ```text
> I am trying to use the free NiceSchedule call schedule solver tutorial.
>
> GitHub repo:
> https://github.com/rumblelab/ai-call-scheduler
>
> Fetch and read AGENTS.md from the repo first. It tells you which
> other files to read, how to talk to me, when to open the rendered
> schedule, and the safety rules. Follow it.
>
> Then help me run the dummy solve exactly as-is. Use the synthetic
> data in data/sample/. Do not ask me for real names or real vacation
> data yet.
>
> Start by explaining what the solver currently does in plain English.
> ```

## The important distinction

An LLM is probabilistic. It predicts text. That is why older models could famously get simple counting questions wrong.

A solver is deterministic. You give it variables, constraints, and an objective. It searches for assignments that satisfy the constraints.

That distinction matters for scheduling. A call schedule has rules:

- someone must cover every required shift
- nobody should be scheduled on vacation
- people need rest between calls
- some clinicians can cover OB and some cannot
- the burden should be reasonably fair

ChatGPT can help you write those rules down. CP-SAT should be the thing that actually chooses the assignments.

## What this v1 solver does

This first version is intentionally simple. It handles:

1. Cover every required shift in `coverage.csv`.
2. Respect shift eligibility in `clinicians.csv`.
3. Block hard vacation and no-call requests in `requests.csv`.
4. Assign each clinician to at most one shift per day.
5. Enforce a minimum rest gap between assignments.
6. Prefer fair total assignment counts.
7. Prefer fair weekend assignment counts.
8. Use prior `history.csv` assignments as part of the fairness picture.
9. Prefer more rest spacing when the hard rules leave room.

That is enough to show the pattern. It is not a production anesthesia scheduler. Real groups add more rules: holiday rotation, partner versus non-partner allocation, site-specific coverage, backup call, post-call recovery, locked assignments, and exceptions that only make sense locally.

## Folder structure

```text
ai-call-scheduler/
  solver.py
  requirements.txt
  README.md
  config/
    sample_rules.json
  data/
    sample/
      clinicians.csv
      requests.csv
      coverage.csv
      history.csv
  output/
    sample_schedule.csv        # written by solver.py
    sample_schedule.html       # printable grid, also written by solver.py
  scripts/
    generate_coverage.py
  docs/
    scheduler-agent-skill.md
    csv-schema.md
    adaptation-cookbook.md
    troubleshooting.md
    agent-privacy.md
```

## Step 1: run the dummy schedule first

Create a virtual environment:

```bash
python3 -m venv .venv
```

Install OR-Tools:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Run the sample solver:

```bash
.venv/bin/python solver.py
```

Expected result:

```text
Status: OPTIMAL
Wrote 28 assignments to output/sample_schedule.csv
```

Open `output/sample_schedule.csv`. You should see assignments for every OR and OB shift in the two-week sample.

Do not move on to your own data until this works.

## Step 2: understand the CSV files

The solver reads four files.

### `clinicians.csv`

One row per clinician.

Important columns:

- `clinician_id`: stable ID used by every other file
- `name`: display name
- `active`: `1` if this person can be scheduled
- `can_or`, `can_ob`: eligibility flags
- `target_shifts`: preferred number of shifts in this schedule
- `max_shifts`: hard maximum shifts
- `target_weekend_shifts`: preferred weekend count
- `max_weekend_shifts`: hard maximum weekend count
- `min_days_between_assignments`: hard rest rule

Use IDs instead of real names while testing. For example: `doc_01`, `doc_02`, `doc_03`.

### `coverage.csv`

One row per required shift type per day.

```csv
date,shift_type,required_count
2026-06-01,OR,1
2026-06-01,OB,1
```

This is the demand side of the schedule. The solver's first job is to fill every row.

### `requests.csv`

Vacation, no-call requests, and soft preferences.

```csv
request_id,clinician_id,start_date,end_date,request_type,hard,shift_type,note
r1,cary,2026-06-05,2026-06-07,vacation,1,,Family trip
```

If `hard` is `1`, the solver must honor it. If `hard` is `0`, the solver tries to avoid it but can override it if coverage needs require it.

If `shift_type` is blank, the request applies to every shift type. If it is filled in, the request applies only to that shift type.

### `history.csv`

Prior assignments used for fairness.

The v1 solver counts prior assignments and tries to avoid making the already-heavy people even heavier.

## Step 3: make your own data folder

After the dummy data works, copy the sample folder:

```bash
cp -R data/sample data/my_data
```

Then edit:

```text
data/my_data/clinicians.csv
data/my_data/requests.csv
data/my_data/coverage.csv
data/my_data/history.csv
```

Update the config:

```json
{
  "input_dir": "data/my_data",
  "output_csv": "output/my_schedule.csv"
}
```

Then run:

```bash
.venv/bin/python solver.py --config config/my_rules.json
```

## Step 4: where the rules live

There are three rule layers.

### 1. Data rules

These live in the CSV files.

Examples:

- Dr. A can cover OB: `can_ob = 1`
- Dr. B cannot cover OR: `can_or = 0`
- Dr. C is on vacation: row in `requests.csv`
- June 1 needs one OR and one OB clinician: rows in `coverage.csv`

### 2. Config rules

These live in `config/sample_rules.json`.

Examples:

- default minimum rest days
- preferred rest spacing
- objective weights for fairness, weekend balance, soft requests, and rest

### 3. Code rules

These live in `solver.py`.

Examples:

- exactly cover every required shift
- block hard requests
- enforce one assignment per day
- calculate fairness penalties

When you ask an AI agent to add rules, tell it which layer the rule belongs in. If the rule can be expressed as data, keep it in CSV. If it changes scoring, put it in config. If it changes the meaning of feasibility, it probably belongs in code.

## Step 5: if you get stuck, hand this to your coding agent

Open `docs/scheduler-agent-skill.md`. That file tells the agent how to think about a call schedule:

- hard constraints versus soft preferences
- coverage first
- vacation blocks
- fairness
- rest spacing
- dummy data before real data

Copy this whole block into Codex, Claude Code, ChatGPT, or another coding assistant:

```text
I am adapting the free NiceSchedule call schedule solver tutorial.

GitHub repo:
https://github.com/rumblelab/ai-call-scheduler

Fetch and read AGENTS.md from the repo first. It tells you what else
to read, how to talk to me, the run/open/report loop, and the safety
rules. Follow it.

Then explain the current rule set back to me in plain English and
help me add this one rule:

[write one rule here]

One rule at a time. After changing it, tell me how to test it.
```

Good first expansion rules:

- Add a holiday column and balance holiday assignments.
- Add a `locked_assignments.csv` file.
- Add a third shift type such as `CARDIAC`.
- Add a rule that nobody gets more than one weekend day in the same weekend.
- Add a soft penalty for assigning someone to their least preferred shift.

## Privacy note

Start with dummy data. Do not paste real physician schedules, vacation history, internal group rules, employment data, or patient information into public tools.

If you use a coding agent, prefer a setup where you understand what data is leaving your machine and what retention settings apply. For the longer version, see `docs/agent-privacy.md`.

## If this feels too complicated

That is useful feedback.

The basic pattern is not magic. The hard part is making it work for a real group: collecting clean requests, importing history, modeling local rules, debugging infeasible schedules, explaining tradeoffs, publishing the final schedule, and maintaining the process every month.

There are two different next steps.

For residents and DIY schedulers:

If you want a simple hosted web version of this free tutorial, email [hello@niceschedule.com](mailto:hello@niceschedule.com?subject=Web%20version%20of%20the%20AI%20schedule%20solver) with the subject line `Web version of the AI schedule solver`.

For real anesthesia groups:

If you do not want your group schedule depending on a vibe-coded script, book a NiceSchedule call. Send us your current spreadsheet and rules: [hello@niceschedule.com](mailto:hello@niceschedule.com?subject=NiceSchedule%20call%20for%20our%20anesthesia%20group).
