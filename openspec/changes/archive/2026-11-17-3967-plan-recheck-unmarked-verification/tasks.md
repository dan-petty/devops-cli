# Tasks

## 1. Behavior

- [x] 1.1 Add failing unit test for rewriting unmarked verification commands
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_rewrite.py` fails on the base
- [x] 1.2 Implement in-place rewrite of unmarked verification commands in plan rewrite
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_rewrite.py` passes

## 2. Documents

- [x] 2.1 Update documentation and message strings for marked verification rewrite
  - Verification: `$ uv run devops ci docs` passes
