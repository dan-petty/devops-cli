# Tasks

## 1. Make the decommission strict

- [x] 1.1 Make `test_the_task_files_are_decommissioned` strict and remove `_LATE_TASK_FILES_GLOB`, and verify that `uv run devops ci test tests/test_architectural_invariants.py` fails while the late task files are in the tree
- [x] 1.2 Delete `docs/agent/tasks/` and the glob `docs/agent/tasks/task-*.md` in `CONST_DOCS_INVENTORY`, and verify that `uv run devops ci test tests/test_architectural_invariants.py tests/test_docs_inventory.py tests/test_pr_cmd.py` passes
- [x] 1.3 Run `uv run devops docs check` and `uv run devops openspec check`, and verify that both pass
