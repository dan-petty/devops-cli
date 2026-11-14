# Proposal

## Why

A `Verification:` span that lacks the `$ ` marker is prose to the reader, so the verification field stays empty and the group looks like an `other` group. The reader then reports that the group has neither `verify` nor `process`, which hides the cause (#4010).

## What Changes

- `parse_task_groups` and the change reader check the code spans of each `Verification:` line for the `$ ` marker before the group kind is inferred.
- An unmarked span raises a diagnostic that names the group and says to add `$ `.
- A marked span, and an inline span outside a `Verification:` line, keep their behavior.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-plan-check`: The reader names an unmarked verification span.

## Impact

- Code: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_task_verification.py`

## Feasibility

- `read_change` already builds each `StageGroup` and raises `PlanReadError` with a message.
- The `Verification:` line is one line, and a regular expression reads its spans.
- Verification commands: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_task_verification.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The parser is this repository's own grammar. The change adds one check beside the existing verification check, and no library.
