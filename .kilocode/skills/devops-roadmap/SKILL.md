---
name: devops-roadmap
description: File, inspect, claim, or return roadmap items on GitHub. Use when you file a bug or idea, check item eligibility, or return an unbuildable item.
---

# Manage Roadmap Items

Use `devops roadmap` to file candidates, inspect item readiness, claim work, or return an item with evidence.

## File, Pivot from Trackers, or Return a Leaf Item

1. Run `uv run devops roadmap intake --title "fix(<scope>): <summary>" --body-file <file> --confirm` to file a new candidate.
2. Never return a tracker or epic (`type/epic` or an issue with sub-issues). Run `uv run devops roadmap explain <item>` (or inspect its sub-issues and related issues) and claim/work an unblocked open sub-issue or related issue instead; if it is an unsplit tracker, file and link its sub-issues.
3. Run `uv run devops roadmap return <item> --comment "<evidence>" --confirm` only when a leaf item cannot be built as specified.

## Inspect and Claim Items

1. Run `uv run devops roadmap inbox` to list items that need attention.
2. Run `uv run devops roadmap explain <item>` to check whether the refine, stage, and implement jobs take the item.
3. Run `uv run devops roadmap claim <item> --as agent --confirm` to claim an item for an agent.
4. Run `uv run devops roadmap release <item> --confirm` to remove the owner label from an item.

## Manage Labels, Milestones and Duplicates

1. Run `uv run devops gh issue edit <item> --add-label <label>` or `--remove-label <label>` to update issue labels, or `--milestone <milestone>` to set a milestone.
2. Run `uv run devops gh label sync` to synchronize repository labels with `.github/labels.yml`.
3. Run `uv run devops gh issue close <item> --reason not-planned --comment-file <file>` to close a duplicate or superseded issue.
