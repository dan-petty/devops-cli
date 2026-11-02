# Proposal

## Why

The stage job plans an item without mapping its acceptance criteria to task groups, so about 10 of 37 plans of 2026-11-01 drop at least one criterion (#3019). No rule asks the model for the mapping and no check refuses a reply that leaves a criterion out.

## What Changes

- Add `StageCriterion` and a `criteria` list to `StageProposal` in `src/devops_cli/roadmap/stage_change.py`.
- Add `criterion_problems` and call it from `check_proposal`, so an acceptance bullet of the issue that no entry maps is a problem of the reply.
- Render a Criteria section in `tasks.md` that lists each criterion with its group number or `pending-person` and reason.
- State the criteria rule in the stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Add the `criteria` gate to the golden-set replay and mark the known dropped-criterion defects of the cases.
- Document the criteria rule in `docs/ROADMAP_WORKFLOW.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: Criteria mapping in the stage reply, Criteria section in tasks.md

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_cases.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`

## Feasibility

- `search_code` for `def check_proposal` showed `src/devops_cli/roadmap/stage_change.py:286`, the gate that the stage job runs on a reply, and `search_code` for `check_proposal(` showed `src/devops_cli/roadmap/stage.py:672`, where the job calls it. The issue's premise holds: the gate checks specs and paths only.
- `read_file` of `src/devops_cli/roadmap/stage_change.py` lines 239-299 showed `StageProposal` with no `criteria` field and `check_proposal` with no criterion rule, so the mapping is missing as the issue says.
- `read_file` of `src/devops_cli/roadmap/stage_change.py` lines 436-473 showed `group_text` and `_tasks_file`, the place where the Criteria section is rendered.
- `search_code` for `def path_problems` showed `src/devops_cli/roadmap/stage_paths.py:141`, the pattern that a pure function of the reply and the issue follows.
- `list_files` of `tests/roadmap` showed the tests that exist: `tests/roadmap/test_roadmap_stage_plan.py` holds the `check_proposal` tests, and `tests/roadmap/test_roadmap_stage_eval_gates.py` holds the replay tests.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` for the new refusal, and `uv run devops roadmap eval stage --replay` for the new gate on the recorded plans.

## Existing Tool Considered

No open, maintained tool covers this need: the mapping is a project-specific rule of the stage job's reply schema. The change builds its own code: a pydantic model, a pure function in `check_proposal`, a prompt line, a `tasks.md` section and tests. Written cost is about 120 lines (roughly 1200 tokens) to build, and keeping it costs a few tokens per schema change; fixing it costs one focused session of 30 to 60 minutes. The change deletes no internal code.
