# Tasks

## 1. Run the rules of the plan check before the stage push

Kind: behavior. Reads: `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_findings.py`, `tests/roadmap/test_roadmap_plan_check.py`, `tests/roadmap/stage/test_roadmap_stage_refused_reply.py`. Changes: `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_findings.py`, `src/devops_cli/commands/roadmap.py`, `tests/roadmap/stage/test_roadmap_stage_plan_check.py` (new), `tests/fixtures/roadmap/plan_heads/5407-ecc08320bf60/` (new), `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_gates.py`, `tests/roadmap/stage/test_roadmap_stage_trace_runs.py`, `tests/roadmap/stage/test_roadmap_stage_plan_record_facts.py`.

- [x] 1.1 Write `tests/roadmap/stage/test_roadmap_stage_plan_check.py`: a reply with a group of the form of group 2 of #5407 goes back to the model with the `group-no-files` line, and a reply that keeps the defect after each return fails the item and pushes no branch. Add the head of #5407 to `tests/fixtures/roadmap/plan_heads/5407-ecc08320bf60/`, and test that the check before the push gives its CI problem word for word and judges no open dependency
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan_check.py`
- [x] 1.2 Add `PlanFolder`, `title_body_problems`, `folder_problems`, `staged_problems` and `PlanProblem.line` to `src/devops_cli/roadmap/plan_check.py`, and make `plan_check` call them on the worktree of the head. Add `PLAN_CHECK_GATE` to `src/devops_cli/roadmap/stage/stage_findings.py`, and run `staged_problems` in `_Planner._settle` of `src/devops_cli/roadmap/stage/stage.py` after `openspec validate`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan_check.py tests/roadmap/test_roadmap_plan_check.py tests/commands/test_roadmap_plan_check_cmd.py`
- [x] 1.3 Name the changed file in the tasks of the plans of `_half` and `_changed` in `tests/roadmap/stage/test_roadmap_stage_plan.py` and of `_plan` in `tests/roadmap/stage/test_roadmap_stage_trace_runs.py`, and plan on the `stage_repo` clone in `tests/roadmap/stage/test_roadmap_stage_gates.py`, `tests/roadmap/stage/test_roadmap_stage_trace_runs.py` and `tests/roadmap/stage/test_roadmap_stage_plan_record_facts.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage tests/roadmap/steps tests/roadmap/test_roadmap_plan_check.py tests/roadmap/test_roadmap_plan_read.py`

## 2. Document the check before the push

Kind: other. Reads: `docs/roadmap/stage.md`, `docs/roadmap/plan-check.md`. Changes: `docs/roadmap/stage.md`, `docs/roadmap/plan-check.md`.

- [x] 2.1 Edit `docs/roadmap/stage.md` so the steps of an item and the returns of a refused reply name the rules of the plan check, and edit `docs/roadmap/plan-check.md` so it says where the folder is read and which rules the stage job runs before the push
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: `tests/roadmap/stage/test_roadmap_stage_plan_check.py` proves that the stage job does not push a plan that fails a rule of the plan check.
- Pending a person: one week after the merge and the release, plan pull requests get at most 1.5 CI runs each, and the `Plan Check` failures of Service plan pull requests fall by half.
