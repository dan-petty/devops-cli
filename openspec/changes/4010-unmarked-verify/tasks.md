# Tasks

## 1. Name the missing marker

Reads: `src/devops_cli/roadmap/plan_read.py`. Changes: the same file, `src/devops_cli/lang/en/messages.py`, and `tests/roadmap/stage/test_roadmap_stage_task_verification.py`.

- [ ] 1.1 Add `_unmarked_verification` and call it before the kind is inferred.
- [ ] 1.2 Add the message.
- [ ] 1.3 Add the three tests.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_task_verification.py` passes
