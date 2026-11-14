# Tasks

## 1. Accept a restoration to base

Reads: `src/devops_cli/roadmap/implement/implement_step.py`. Changes: the same file and `tests/roadmap/implement/test_roadmap_implement_step_repair.py`.

- [x] 1.1 Add `base` to `_foreign_change` and allow a path whose staged content matches `base`.
- [x] 1.2 Pass `keeper.base` from `_extra_turn`.
- [x] 1.3 Add the tests: a restoration, a foreign edit, and a deleted base file.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_repair.py` passes
