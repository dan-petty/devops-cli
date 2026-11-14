# Tasks

## 1. Share the dependency check

Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/implement/implement.py`. Changes: the same files, `src/devops_cli/roadmap/dependencies.py`, and `tests/roadmap/implement/test_roadmap_implement_selection.py`.

- [x] 1.1 Add `open_dependency` and `open_issue_dependencies` in `src/devops_cli/roadmap/dependencies.py`.
- [x] 1.2 Replace the stage private check with the shared helper.
- [x] 1.3 Add the body and plan checks to the implement judge.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_selection.py tests/roadmap/stage/test_roadmap_stage_selection.py` passes
- [x] 1.4 Add the three tests: open body, open plan, closed dependencies.
  - Verification: the same test command passes
