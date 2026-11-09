---
name: devops-review
description: Run AI-powered code reviews and inspect session findings. Use when you review a branch, pull request, or path, or when you inspect review findings.
---

# Run a Code Review and Inspect Findings

Use `devops review` to audit source files, branch diffs, or pull requests, and to inspect structured findings.

## Run a Review

1. Run `uv run devops review branch` to review the current branch diff against `main`.
2. Run `uv run devops review path <targets>` to review specific files or directories directly.
3. Run `uv run devops review pr <number>` to review a GitHub pull request.

## Inspect Findings and Statistics

1. Run `uv run devops review findings --details` to inspect the findings of the latest session.
2. Run `uv run devops review findings --candidates --details` to inspect all candidates, including invalidated ones.
3. Run `uv run devops review stats` to display accuracy statistics across saved review sessions.
4. Run `uv run devops review export-feedback` to append verdicts to the feedback dataset.
