# Agent Setup and Privacy Notes

This is a brief disclosure, not legal advice.

The solver runs locally: it reads CSVs from this repo and writes schedules to `output/`.

The AI assistant is separate. When you use a chat tool or coding agent, your messages and the file context it reads may be sent to that tool's AI provider. Use the tool settings and data-sharing approach that fit your group.

Real display names are fine if you are comfortable using them in your local workflow. IDs or fake names are useful for public examples, support requests, or more sensitive schedules.

## Agent Prompt

```text
Help me adapt this scheduler in this local repo.
The solver runs locally, but I understand the AI tool may receive chat and file context. Use real display names if they are already in my local CSVs.
Before changing code, explain which rule you are adding and how we will test it.
```
