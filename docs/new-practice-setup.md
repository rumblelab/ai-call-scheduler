# Setting up a new practice for the first time

Use this once the sample solve has worked and the chief is ready to build their real group's schedule. From here on you're working in `data/my_data/` and `config/my_rules.json`, not the tutorial files.

## Open the conversation

One natural-language question, in your own words — *"tell me about the schedule you're trying to build: how many people, what shifts, what time period?"* Then have a conversation. Don't present a structured multi-choice question or a numbered checklist of follow-ups. Take what they give you, fill in sensible defaults where appropriate, and iterate.

You eventually need enough to fill `clinicians.csv`, `coverage.csv`, `requests.csv`, and `history.csv` — but you don't need to extract all of it up front.

## The four required asks

You must explicitly ask about all four before the first solve. Skipping any of them either silently breaks fairness or surprises the chief after they see the schedule — both erode trust and force a re-solve.

### 1. Roster + eligibility

Who's on staff, and what shifts each person can cover. Goes into `data/my_data/clinicians.csv`.

Default to leaving `clinician_id` blank and using real display names — the solver derives the id from the name (`Alice Smith` → `alice_smith`), and `requests.csv` accepts names verbatim. Use synthetic ids only if the chief prefers them, or for public/sensitive examples.

### 2. Coverage pattern

Which shifts run on which days. Drives `data/my_data/shift_pattern.csv` — rows of `shift_type,weekday_mask,required_count` where `weekday_mask` is 7 characters Mon–Sun:

- `1111100` = weekdays only
- `0000011` = weekends only
- `1111111` = every day

After you have the pattern, generate the coverage file for the target month:

```bash
.venv/bin/python scripts/generate_coverage.py --year 2026 --month 7
```

If the chief mentions a new shift type (a second location, a backup call, anything beyond what's in the sample), add the matching `can_<shift>` column to `clinicians.csv` or the solver will refuse to run.

### 3. Vacation / no-call requests

Even if the answer is *"nobody is out this month,"* you must explicitly ask. Chiefs routinely forget to volunteer this; if you skip the ask, the solver assumes everyone is fully available and the chief catches the problem only after seeing someone scheduled on their kid's birthday. Don't make them re-solve.

### 4. Recent call history

Even if the answer is *"we're starting fresh, no prior data,"* you must explicitly ask. Without it, "fair" means fair against nothing, and whoever covered the last three weekends in a row gets stacked again. The solver also has a built-in soft preference (`weekday_repeat`) that *only* works if history is loaded — skipping the ask silently disables one of the fairness terms.

Most chiefs have the data sitting in a spreadsheet, screenshot, or old PDF but won't volunteer it. Offer in plain language:

> *"Do you have the last month or two of call somewhere — spreadsheet, screenshot, PDF? I'll use it as a fairness baseline so we don't double up on whoever covered last month. If not, no problem, we'll start fresh."*

When they send it, translate it into `history.csv` (rows of `date, clinician_id, shift_type`) — same pattern as turning messy vacation emails into `requests.csv`. From the second solve forward, `scripts/start_next_month.py` keeps history current automatically.

## What you don't need to ask up front

Pick these up as the conversation surfaces them — no need to interview:

- The time window (one month, three months, a year).
- What fairness means to the chief (totals, weekends, holidays).
- Display names vs. short IDs.

## Run the configured solve

Once `data/my_data/` and `config/my_rules.json` exist:

```bash
.venv/bin/python scripts/run_my_schedule.py
```

This first runs a preflight (`scripts/check_my_data.py`) that prints a Capacity summary — per-shift demand vs. eligible doctors' combined max, with a "tight" tag when headroom is thin. Glance at it before the solve output; if anything is short or tight, translate it into plain English for the chief (e.g. *"OR coverage is tight this month — any extra vacation may make it hard to schedule"*), never quote headroom numbers.

Then give the usual post-solve report: whether it found a valid schedule (in plain words, not "OPTIMAL"), how many shifts it filled, anything that was tight named in human terms, and one open question about what to adjust.
