# Tasks

## 1. The row runs on the status lane

- [x] Write failing tests in `tests/test_roadmap_run.py` and `tests/test_roadmap_implement_submit.py`: the status lane holds `metrics` and then `implement` and the model lane holds `intake`, `refine`, `stage` and `alternatives`; with a refine round that has not ended, a poll runs `implement` on the status lane; a poll makes the row due by its interval on the status lane; a webhook batch makes the row due no sooner than its interval; a ledger record that holds an `implement` entry loads and keeps the row suspended on the status lane.
  - Verification: `uv run devops ci test tests/test_roadmap_run.py tests/test_roadmap_implement_submit.py`
- [x] Move the row from `MODEL_LANE_ROWS` to `STATUS_LANE_ROWS` in `src/devops_cli/roadmap/run.py`, and update the docstrings of `run.py` and the comment of the lanes in `src/devops_cli/config/constants.py`. Update the tests that name the lane of the row.
  - Verification: `uv run devops ci test tests/test_roadmap_run.py tests/test_roadmap_implement_submit.py tests/test_server_service.py`

## 2. Two writers of one issue

- [x] Write tests in `tests/test_roadmap_github_store.py`: two stores on one fake issue, a field write with a refine mark against a mark write of `implement.job`, and a body write against a mark write. Each keeps all keys. Check that both fail when the lock of the store is taken out.
  - Verification: `uv run devops ci test tests/test_roadmap_github_store.py`

## 3. A suspended row wakes with no webhook

- [x] Write a failing test in `tests/test_roadmap_run.py`: three failed poll rounds suspend `implement`, the fault is fixed, and a poll round of a later hour runs the row. Add the hour of the round to the input of a round of a lane that reads no change (`_round_input` in `src/devops_cli/roadmap/run.py`).
  - Verification: `uv run devops ci test tests/test_roadmap_run.py`

## 4. The documentation

- [x] Name the lane of each row in `CONTEXT.md` (Lane) and in `k8s/README.md` (Roadmap service, step 16 and the rows list), and regenerate the documentation.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 5. Archive

- [x] Archive the change.
  - Verification: `uv run devops openspec archive 2757-implement-status-lane`
