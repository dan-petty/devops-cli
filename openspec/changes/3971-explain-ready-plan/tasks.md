# Tasks

## 1. Name the merge wait

Reads: `src/devops_cli/roadmap/implement/implement.py`, `src/devops_cli/lang/en/messages.py`. Changes: the same files and `tests/roadmap/implement/test_roadmap_implement_selection.py`.

- [ ] 1.1 Add `implement_left_plan_ready` and return it from `_pull_reason` for an open plan pull request that is no longer a draft.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_selection.py` passes
- [ ] 1.2 Add the tests: the ready plan message, and the old message for a closed plan.
  - Verification: the same test command passes
