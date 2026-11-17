# Proposal: #4969

## Why

The `branch-current` pre-push hook stops its `git fetch` of `origin/main` after 20 seconds. A loaded
devcontainer needs longer, so the hook refuses a push of a current branch and says that origin is
unavailable. Closes #4969.

## What Changes

- The fetch limit is 24 seconds, inside the 120 second agent shell budget with the other pre-push
  hooks (40 and 30 seconds).
- A fetch that exits with status 124 prints a message that names 24 seconds and no unavailable
  origin.
- A fetch that exits with another status keeps the unavailable-origin message.
- Pytest tests run the hook with a stub `git` for the timeout and failure, and check the budget.

## Capabilities

### Modified

- `pre-push-branch-current`: the hook bounds its fetch and names a timeout.

## Impact

A push of a current branch passes on a busy host whose fetch takes between 20 and 24 seconds. A
timeout message names the limit, and an unavailable origin keeps its own message.

## Feasibility

Confirmed against the issue and the code: the `branch-current` entry of
`.pre-commit-config.yaml` holds `timeout 20 git fetch`, and `tests/git/test_branch_current_hook.py`
already runs the entry in a real repository. The other pre-push entries hold `timeout 40` and
`timeout 30`.

## Existing Tool Considered

No open tool or library covers the need. The alternatives check of 2026-11-15 returned `none`; only
hook-runner images and generic git and timeout documentation exist. The change stays in the
repository's own hook script and its test, with no dependency.
