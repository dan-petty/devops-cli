# Tasks

## 1. Refuse a behavior verify that runs no test

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_form.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`. Changes: `src/devops_cli/roadmap/stage/stage_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_form.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`.

- [x] 1.1 Add the rule to `form_problems` for a `behavior` group, with the problem text in `RoadmapMessages`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_form.py` passes
- [x] 1.2 Add the four cases: no test module, a test directory, the group's own module, and an `other` group
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_form.py` passes
- [x] 1.3 Keep the existing plan tests true, where a test of the path rule uses a behavior group with a verify of another module
  - Verification: `$ uv run devops ci test tests/roadmap/stage` passes

## 2. Run the gates

Kind: other. Reads: `tests/roadmap/`. Changes: none.

- [x] 2.1 Run the gate of the branch
  - Verification: `$ uv run devops ci --check --only lint,format,typecheck` passes
  - Verification: `$ uv run devops ci docs` passes
