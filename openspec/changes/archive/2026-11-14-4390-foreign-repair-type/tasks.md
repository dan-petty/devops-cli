# Tasks

## 1. Type the foreign-change stop

Reads: `src/devops_cli/roadmap/implement/implement_step.py`. Changes: the same file and `tests/roadmap/implement/test_roadmap_implement_step_repair.py`.

- [x] 1.1 Pass `FailureClass.OUTSIDE_PLAN` at the `_Failure(foreign)` site.
- [x] 1.2 Assert the class in the repair-turn test.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_repair.py` passes
