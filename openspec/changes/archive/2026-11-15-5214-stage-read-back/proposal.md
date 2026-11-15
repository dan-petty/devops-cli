# Proposal: #5214

## Why

The stage job does not read back the files that it pushes (#5214).

- The writer accepts texts that the reader refuses. Two `other` groups that `StageProposal` and `form_problems` accept fail `read_change` with "has both verify and process": a `process` that ends with "verify that `uv run devops ci docs` passes" (`_INLINE_VERIFY`), and an `implementation` that holds the process mark (`_split_process`).
- A stage run that pushes an unreadable change gets no error. The advisory `Plan Check` job fails later, and the item gets no timely recovery.
- A fact mismatch between the proposal and the read-back files is a defect of the writer or reader. It needs a failure class with a bounded retry and a defect count.

Closes #5214.

## What Changes

- In `_Planner._settle`, after `openspec validate` passes, read rendered files with `read_change`.
- A `PlanReadError` returns a refusal of the gate `read` (`READ_GATE` in `stage_findings.py`) with the reader reason. The reply goes back through gate returns.
- Pure function `plan_read.read_back_problems(files, proposal)` compares groups, unchanged references, and criteria against `file_facts(proposal)`. A difference raises `RoadmapPlanReadBackError` with the differences and no text of the plan.
- New failure class `plan_unreadable` in `roadmap/failure.py`. `CLASS_BY_EXCEPTION` maps `RoadmapPlanReadBackError` to it before `RoadmapStageError`. `ACTION_BY_CLASS` gives `wait`. `RETRY_AFTER` gives 6 hours.
- `_record_failures` counts `plan_unreadable` with `plan_defect` on the same body toward `roadmap.stage.plan_defect_limit`. The third failure returns the item to New with the comment.
- In `fix-plan`, a revision that fails read-back results in `failed` (no gated plan, 0 pushes) or `regated` (pushes gated plan) with class `plan_unreadable`.
- `fix_plan_request_conditions["push"]` states that the pushed plan reads back.
- Documentation and spec updates for the new class and read-back gate.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-failure-taxonomy`: add `plan_unreadable` with wait action and 6-hour retry.
- `roadmap-stage/returns`: include `plan_unreadable` in the defect limit count on one body.

## Impact

- Code:
  - `src/devops_cli/exceptions/roadmap.py`
  - `src/devops_cli/roadmap/failure.py`
  - `src/devops_cli/roadmap/stage/stage.py`
  - `src/devops_cli/roadmap/stage/stage_findings.py`
  - `src/devops_cli/roadmap/plan_read.py`
  - `src/devops_cli/roadmap/plan_recheck.py`
  - `src/devops_cli/lang/en/messages.py`
- Tests:
  - `tests/roadmap/stage/test_roadmap_stage_plan.py`
  - `tests/roadmap/stage/test_roadmap_stage_failure_class.py`
  - `tests/roadmap/stage/test_roadmap_stage_retry_after.py`
  - `tests/roadmap/stage/test_roadmap_stage_plan_defect_limit.py`
  - `tests/roadmap/test_roadmap_plan_read.py`
  - `tests/roadmap/test_roadmap_failure.py`
  - `tests/roadmap/steps/test_roadmap_fix_plan.py`
  - `tests/commands/test_roadmap_step_fix_plan.py`
- Documentation:
  - `docs/ROADMAP_WORKFLOW.md`
  - `docs/adr/0019-a-decision-step-asks-jev-short-closed-questions-about-evidence-that-tools-extract.md`
  - `docs/CLUSTER.md`
  - `docs/roadmap/stage.md`
  - `docs/roadmap/job-success.md`
  - `openspec/specs/roadmap-failure-taxonomy/spec.md`
  - `openspec/specs/roadmap-stage/returns/spec.md`

## Feasibility

- Premise confirmed: `stage.py` currently does not call `read_change`.
- `read_change` and `file_facts` exist in `src/devops_cli/roadmap/plan_read.py`.
- `CLASS_BY_EXCEPTION` and `RETRY_AFTER` exist in `src/devops_cli/roadmap/failure.py`.

## Existing Tool Considered

Reuses `read_change`, `file_facts`, and existing stage gate-return mechanics. No new dependency added. Cost to build: 0.8M tokens.
