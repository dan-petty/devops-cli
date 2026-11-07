# Tasks

## 1. The four roadmap test files are split by behaviour (test-only edits)

- [ ] 1.1 Split `tests/roadmap/test_roadmap_run.py` into the 13 `test_roadmap_run_*.py` files, and move the helpers that several of them use to `tests/support/roadmap_run.py`.
  Verification: `uv run pytest tests/roadmap/test_roadmap_run_due_table.py tests/roadmap/test_roadmap_run_service.py tests/roadmap/test_roadmap_run_checkout.py tests/roadmap/test_roadmap_run_metrics.py tests/roadmap/test_roadmap_run_intake_row.py tests/roadmap/test_roadmap_run_github_requests.py tests/roadmap/test_roadmap_run_lanes.py tests/roadmap/test_roadmap_run_failure_ledger.py tests/roadmap/test_roadmap_run_errors.py tests/roadmap/test_roadmap_run_scoped_update.py tests/roadmap/test_roadmap_run_job_rows.py tests/roadmap/test_roadmap_run_job_counts.py tests/roadmap/test_roadmap_run_adapter_imports.py`
- [ ] 1.2 Split `tests/roadmap/refine/test_roadmap_refine.py` into the 21 `test_roadmap_refine_*.py` files of the proposal, move its shared helpers to `tests/support/roadmap_refine.py`, and rename its snapshot to follow its test.
  Verification: `uv run pytest tests/roadmap/refine`
- [ ] 1.3 Split `tests/roadmap/intake/test_roadmap_intake.py` into the 15 `test_roadmap_intake_*.py` files of the proposal, move its shared helpers to `tests/support/roadmap_intake.py`, and rename its snapshot to follow its test.
  Verification: `uv run pytest tests/roadmap/intake`
- [ ] 1.4 Split `tests/roadmap/stores/test_roadmap_github_store.py` into the 11 `test_roadmap_github_store_*.py` files, and move its shared helpers to `tests/support/roadmap_github_store.py`.
  Verification: `uv run pytest tests/roadmap/stores`
- [ ] 1.5 Check that the four old files are gone.
  Verification: `! ls tests/roadmap/test_roadmap_run.py tests/roadmap/refine/test_roadmap_refine.py tests/roadmap/intake/test_roadmap_intake.py tests/roadmap/stores/test_roadmap_github_store.py`

## 2. The tests keep their names and the tree keeps its rules (test-only edits)

- [ ] 2.1 Collect the test ids of `tests/roadmap` on the base commit and on the changed tree, and compare the names without the file part. The two lists are equal (5,049 ids).
  Verification: `uv run pytest --collect-only -q tests/roadmap`
- [ ] 2.2 Check that the test tree mirrors the source tree and that no test file imports another test file or a conftest.
  Verification: `uv run pytest tests/invariants tests/gate`

## 3. No stale name is left (documents)

- [ ] 3.1 Fix the path of the old store test file in the docstring of the store contract suite.
  Verification: `! git grep -n -e tests/test_roadmap_github_store.py -- tests src docs README.md ARCHITECTURE.md CONTRIBUTING.md SECURITY.md`
- [ ] 3.2 Check that the change folder is valid.
  Verification: `uv run devops openspec check`
