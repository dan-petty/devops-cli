---
name: devops-roadmap
description: File, inspect, claim, or return roadmap items on GitHub. Use when you file a bug or idea, check item eligibility, or return an unbuildable item.
---

# Manage Roadmap Items

Use `devops roadmap` to file candidates, inspect item readiness, claim work, or return an item with evidence.

## File or Return an Item

1. Run `uv run devops roadmap intake --title "fix(<scope>): <summary>" --body-file <file> --confirm` to file a new candidate.
2. Run `uv run devops roadmap return <item> --comment "<evidence>" --confirm` to return an unbuildable item to `New`.

## Inspect and Claim Items

1. Run `uv run devops roadmap inbox` to list items that wait for a person.
2. Run `uv run devops roadmap explain <item>` to check whether the refine, stage, and implement jobs take the item.
3. Run `uv run devops roadmap claim <item> --as agent --confirm` to claim an item for an agent.
4. Run `uv run devops roadmap release <item> --confirm` to remove the owner label from an item.
