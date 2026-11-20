# Tasks

## 1. Behavior

- [x] 1.1 A command test shows that a confirmed round in a runner calls the runner check, `deny_environment_reads`, `adopt_orphans` and then the step
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_step_fix_checks.py`
- [x] 1.2 The command calls the two functions after `require_runner`
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_step_fix_checks.py`
