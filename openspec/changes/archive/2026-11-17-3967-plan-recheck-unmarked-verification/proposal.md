# Proposal: #3967

## Why
The plan recheck rewrite appends a duplicate verification line instead of rewriting an existing line that lacks the command marker.
A verification command in `tasks.md` must start with `$ `.
Any code span without `$ ` is treated as prose.
Because `group.verification_commands` returns an empty tuple for unmarked lines, `_verification` appends a duplicate generated line and leaves later tasks unmarked.
Closes #3967.

## What Changes
Prepend `$ ` to the command code span of each existing unmarked `Verification:` line in place.
Skip adding a generated `Verification:` line when the group already holds a `Verification:` line.
Add a note for each marked verification command.

## Capabilities
`devops roadmap plan-recheck` marks unmarked verification commands in `tasks.md` without duplicating lines.

## Impact
Merged plans with unmarked verification commands are rewritten cleanly to pass plan check.
No breaking changes or new dependencies.

## Feasibility
Confirmed in `src/devops_cli/roadmap/plan_rewrite.py` and `tests/roadmap/test_roadmap_plan_rewrite.py`.

## Existing Tool Considered
No open, maintained tool or library covers this repository-specific rewrite of `tasks.md`.
The change edits existing code in `src/devops_cli/roadmap/plan_rewrite.py`.
It adds no dependency.
