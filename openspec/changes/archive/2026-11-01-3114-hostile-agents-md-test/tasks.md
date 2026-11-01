# Tasks

## 1. Compare the filled prompt

Reads: `tests/roadmap/test_roadmap_implement_step_rules.py` lines 140 to 162, `src/devops_cli/roadmap/implement_shell_policy.py` lines 195 to 210. Changes: `tests/roadmap/test_roadmap_implement_step_rules.py`.

This group changes one test. The repeatable check is the test run in 1.1 and 1.2.

- [x] 1.1 Run `uv run pytest tests/roadmap/test_roadmap_implement_step_rules.py -k hostile -n0` on `origin/main` and see it fail with `(False, True, True)`
- [x] 1.2 Compare `inputs.instructions` with `fill_prompt(load_task_prompt("roadmap_implement_step.md"))`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_step_rules.py` passes
