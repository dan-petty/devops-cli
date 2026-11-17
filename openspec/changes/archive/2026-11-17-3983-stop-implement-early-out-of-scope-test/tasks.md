# Tasks

## 1. Behavior

- [x] 1.1 Add failing offline test for out-of-scope test failure early stop
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_repair.py` fails on the base
- [x] 1.2 Implement early stop for out-of-scope test failure in implement step exit checks
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_repair.py` passes

## 2. Documents

- [x] 2.1 Add message string and documentation for out-of-scope test failure early stop
  - Verification: `$ uv run devops ci docs` passes
