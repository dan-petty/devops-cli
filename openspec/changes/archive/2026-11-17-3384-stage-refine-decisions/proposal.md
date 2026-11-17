# Proposal: #3384

## Why

PR #3323 planned issue #3307 with empty decisions and empty rejected alternatives. The refine block in the issue body held five key questions with chosen decisions and rejected alternatives. The stage planner wrote none of them because `roadmap_stage_change.md` never told the planner to read the refine block, and `stage_change.py` allowed an empty design (#3384).

## What Changes

- Update `src/devops_cli/ai/tasks/roadmap_stage_change.md` to tell the planner that the refine block holds a proposed design, and instruct it to carry the chosen decisions and rejected alternatives into `decisions` and `rejected`.
- Add `refine_decisions` in `src/devops_cli/roadmap/stage/stage_criteria.py` to extract `Chosen` and `Rejected` lines from the refine block.
- In `src/devops_cli/roadmap/stage/stage_change.py`, refuse a plan when the issue body holds a refine block with `Chosen` or `Rejected` lines and the plan gives no decision or no rejected alternative.
- Add error messages to `src/devops_cli/lang/en/messages.py`.
- Add tests in `tests/roadmap/stage/test_roadmap_stage_content.py` and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/criteria`: Refine design kept in stage plan.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_criteria.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Tests: `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

## Feasibility

- The refine block markers `<!-- devops-roadmap-refine:start -->` and `<!-- devops-roadmap-refine:end -->` are already parsed in `stage_criteria.py`.
- `check_proposal` already receives `issue_body`.
- Proved with offline unit tests.

## Existing Tool Considered

The existing Markdown and regex parsing in `stage_criteria.py` covers the parsing. No new external tool is needed.
