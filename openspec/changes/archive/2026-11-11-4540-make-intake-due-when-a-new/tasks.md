# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests: a lost delivery of a new issue makes intake due at the next poll, a new pull request does not, a decided new issue costs no model request, and both stores read the newest issue alike
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Add `newest_issue_number` to the store protocol, the GitHub store and the in-memory fake
  - Verification: `$ uv run pytest tests/roadmap/stores/test_roadmap_store_contract.py tests/roadmap/stores/test_roadmap_github_store_changes.py -k newest`
- [x] 1.3 Keep `newest` in the intake record and make intake due on a newer issue
  - Verification: `$ uv run pytest tests/roadmap/test_roadmap_run_scoped_update.py tests/roadmap/test_roadmap_run_due_table.py tests/roadmap/test_roadmap_run_intake_row.py`

## 2. Documents

- [x] 2.1 Tell when the Service runs intake in `docs/roadmap/intake.md`, and name the new issue in the help of `devops roadmap run`
  - Verification: `$ uv run devops ci docs`
