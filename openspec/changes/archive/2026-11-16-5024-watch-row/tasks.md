# Tasks

## 1. Behavior

- [x] 1.1 Add table tests for `due_steps(state)` covering all verdicts for bot and person pull requests
  - Verification: `$ uv run pytest tests/roadmap/steps/test_roadmap_due_steps.py`
- [x] 1.2 Implement `due_steps(state)` pure routing function
  - Verification: `$ uv run pytest tests/roadmap/steps/test_roadmap_due_steps.py`
- [x] 1.3 Add row tests for `watch` row with fake GitHub verifying 1 GraphQL request and 30m failed head backoff
  - Verification: `$ uv run pytest tests/roadmap/test_roadmap_watch_row.py`
- [x] 1.4 Implement `watch` row and ledger persistence in `src/devops_cli/roadmap/watch_row.py`
  - Verification: `$ uv run pytest tests/roadmap/test_roadmap_watch_row.py`
- [x] 1.5 Update `src/devops_cli/roadmap/run.py` to replace `stage_ready` and `pr_conflicts` with `watch`
  - Verification: `$ uv run pytest tests/roadmap/test_roadmap_run_due_table.py`
- [x] 1.6 Verify dry run sends zero requests
  - Verification: `$ uv run pytest tests/roadmap/test_roadmap_watch_row.py -k dry_run`

## 2. Documents

- [x] 2.1 Update `docs/ROADMAP_WORKFLOW.md` and `k8s/README.md`
  - Verification: `$ uv run devops docs check`
