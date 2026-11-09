# Tasks

## 1. Add messages and gate defect quote check to stage plan checks

Reads: `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_plan.py`, write tests first for gate defect checks: refusing a plan that changes a gate file when feasibility quotes no code span, refusing when the test task omits `fails on the base`, refusing when the test task has `skip` and no decision, rejected alternative or spec delta has `non-goal`, accepting when feasibility quotes the code span and the test task holds that span and `fails on the base`, accepting when a non-goal is present for a skipped case, and accepting a plan that changes no gate file.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py` fails on the base
- [x] 1.2 In `src/devops_cli/lang/en/messages.py`, add `stage_problem_gate_defect_quote`, `stage_problem_gate_defect_test`, and `stage_problem_gate_non_goal` to `RoadmapMessages`.
  - Verification: `$ uv run ruff check src/devops_cli/lang/en/messages.py` passes
- [x] 1.3 In `src/devops_cli/roadmap/stage/stage_change.py`, implement `_gate_defect_problems` and `_has_non_goal` and call `_gate_defect_problems` from `content_problems`. Export `GATE_DEFECT_PATHS`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py` passes
