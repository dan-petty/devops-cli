# Tasks

## 1. Read the plan checks

Reads: `src/devops_cli/roadmap/implement/implement.py`. Changes: the same file, `src/devops_cli/lang/en/messages.py`, and `tests/roadmap/implement/test_roadmap_implement_selection.py`.

- [ ] 1.1 Add the check read and `_check_reason` to `_pull_reason`.
- [ ] 1.2 Add the four messages.
- [ ] 1.3 Add `check_reader` to `plan_implement` and to the test helper.
- [ ] 1.4 Add the tests: fail, cancel, pending, unread and pass.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_selection.py` passes
