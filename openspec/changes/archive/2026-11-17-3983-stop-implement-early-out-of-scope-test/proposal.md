# Proposal: #3983

## Why
The implement runner continues to attempt repairs when a test fails outside the `Changes:` list.
`diff_scope` forbids editing files outside `Changes:`.
The runner loops until it reaches `LimitReached` and blocks the item.
Stopping the step early preserves the token budget and returns the item to New with the failing test and path as evidence.
Closes #3983.

## What Changes
Add an early stop in the step exit checks when a test outside the group's `Changes:` list fails.
Name the failing test and the path outside `Changes:` in the stop message.
Classify the stop as `premise_false` so no repair turn or fix step runs.
Add an offline unit test covering this behavior.

## Capabilities
The implement runner detects out-of-scope test failures and stops before spending tokens on disallowed edits.

## Impact
Items with out-of-scope test failures stop immediately and return to New for plan correction.
No breaking changes or new dependencies.

## Feasibility
Confirmed against `src/devops_cli/roadmap/implement/implement_step.py` and `tests/roadmap/implement/test_roadmap_implement_step_repair.py`.

## Existing Tool Considered
No open, maintained tool or library covers this need.
The early-stop guard is internal to the implement runner.
The change edits existing code in `src/devops_cli/roadmap/implement/implement_step.py`.
It adds no dependency.
