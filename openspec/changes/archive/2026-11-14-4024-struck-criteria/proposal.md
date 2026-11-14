# Proposal

## Why

`acceptance_criteria` reads a checklist item under `Acceptance criteria` as an active criterion even when a strikethrough wraps it. A maintainer strikes out a criterion to cancel it, and the planner then plans and validates the dropped text (#4024).

## What Changes

- `acceptance_criteria` omits a list item whose text starts and ends with `~~` and is longer than four characters.
- An active item with an inline `~~` span keeps its text.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/criteria`: A struck-through acceptance criterion is not a criterion.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_criteria.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_criteria.py`

## Feasibility

- The parser already builds the text of each item and strips the task marker.
- A strikethrough that wraps the item begins and ends the text; an inline span does not.
- Verification commands: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_criteria.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The Markdown parser already gives the inline text. The change adds one condition, and no library.
