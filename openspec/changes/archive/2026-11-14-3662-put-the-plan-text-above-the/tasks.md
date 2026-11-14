# Tasks

## 1. Read the plan text above Plans

Kind: behavior. Reads: `src/devops_cli/roadmap/pull_form.py`, `CONTRIBUTING.md`. Changes: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`, `CONTRIBUTING.md`, `tests/roadmap/test_roadmap_pull_form.py`, `tests/roadmap/stage/test_roadmap_stage_apply.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`.

- [x] 1.1 Read the text above `Plans` and give a short plan body the message that names `Plans` and the direction
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_form.py` passes
- [x] 1.2 Write `why`, then `Plans`, then `Change:` in `build_plan_body`, and state the order in CONTRIBUTING.md and the docstring
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_pull_form.py` passes
- [x] 1.3 Update the stage tests that pin the old body order
  - Verification: `$ uv run devops ci test tests/roadmap/stage` passes

## 2. Run the gates

Kind: other. Reads: `tests/roadmap/`. Changes: none.

- [x] 2.1 Run the gate of the branch
  - Verification: `$ uv run devops ci --check --only lint,format,typecheck` passes
  - Verification: `$ uv run devops ci docs` passes
