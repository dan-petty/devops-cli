# Proposal

## Why

The plan reader splits a pending-person line at the first `, `, so an acceptance criterion that holds a comma loses part of its text to the reason. `criterion_problems` then reports the whole criterion as unmapped, and `devops roadmap plan-check` fails on a correct plan (#4023).

## What Changes

- `criterion_problems` resolves each pending-person entry against the acceptance criteria of the issue. When the joined criterion and reason starts with an issue criterion and a comma, the entry takes that criterion and the rest becomes the reason. The longest match wins.
- A pending-person entry that matches no issue criterion is still reported.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/criteria`: A pending-person criterion with a comma maps to the whole text.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_criteria.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_criteria.py`

## Feasibility

- `criterion_problems` already holds the issue body and reads its acceptance criteria.
- `StageCriterion` is a model, so a resolved entry is a copy with a new criterion and reason.
- Verification commands: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_criteria.py tests/roadmap/test_roadmap_plan_read.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

No library reads this repository-specific line form. The issue's own criteria resolve the comma, as the design asks, and the parser keeps its separator.
