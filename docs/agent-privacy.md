# Agent Setup and Privacy Notes

This is not legal advice. It is a practical checklist for using AI tools around scheduling data.

## Start with dummy data

Do not begin with real names, real vacation requests, real call history, hospital identifiers, or patient information. Prove the solver works with synthetic data first.

Use IDs like:

```text
doc_01
doc_02
doc_03
```

Replace those IDs with real names only if your group is comfortable with the tool and workflow.

## Know where your data goes

Before pasting schedule data into any AI tool, check:

- whether prompts are retained
- whether prompts can be used for model improvement
- whether your organization allows the tool
- whether a business agreement or enterprise setting is required
- whether private employment or medical operations data is allowed

Even when there is no patient information, physician schedules and vacation requests can still be sensitive.

## Prefer a local-folder workflow

Coding agents such as Codex or Claude Code can work against files in a local folder. That is usually a better workflow than pasting large CSVs into a chat window, because the agent can inspect the files, edit code, run tests, and keep changes organized.

Still, local-folder agents may send context to a model provider depending on the product and settings. Check the tool's documentation and your organization's policies.

## Minimum safe workflow

1. Run the sample solver on dummy data.
2. Replace names with IDs before adding your own data.
3. Add one real rule at a time.
4. Keep generated schedules out of public GitHub issues.
5. Share only synthetic examples when asking for help.

## Good agent prompt

```text
Help me adapt this solver using synthetic data only.
Do not ask me for real names or private schedules.
If you need an example, invent fake clinicians and fake requests.
Before changing code, explain which rule you are adding and how we will test it.
```
