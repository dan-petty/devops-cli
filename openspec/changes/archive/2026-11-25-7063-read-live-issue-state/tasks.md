# Tasks

## 1. Read live GitHub issue state when freshness is required

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/status_sync.py`, `src/devops_cli/roadmap/stage/stage_job.py`, `src/devops_cli/roadmap/fix_checks_row.py`, `src/devops_cli/roadmap/stop_clear.py`, `tests/support/fakes/roadmap_store.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/status_sync.py`, `src/devops_cli/roadmap/stage/stage_job.py`, `src/devops_cli/roadmap/fix_checks_row.py`, `src/devops_cli/roadmap/stop_clear.py`, `tests/support/fakes/roadmap_store.py`, `tests/roadmap/stores/test_github_store_brain.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`.
Adds: `fresh` parameter on `RoadmapStore.item` and `RoadmapStore.issue`.

- [x] 1.1 Add failing tests in `tests/roadmap/stores/test_github_store_brain.py` for `fresh=True` bypassing fresh cache entries and in `tests/roadmap/implement/test_roadmap_implement_submit.py` for `_report` against `GitHubRoadmapStore` with stale `brain-issue` cache.
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_github_store_brain.py tests/roadmap/implement/test_roadmap_implement_submit.py`
- [x] 1.2 Add `*, fresh: bool = False` to `item` and `issue`, implement conditional/live bypass in `GitHubRoadmapStore.issue`, pass `fresh=True` in `implement_submit._fresh`, `status_sync._read_back`, `stage_job.check_in`, `stage_job._return_for_split`, `fix_checks_row._record_unit`, and `stop_clear._clear_one`, and re-evaluate `_settles_as_stop` before `write_status` in `implement_submit._report`.
  - Verification: `$ uv run devops ci test tests/roadmap/stores/test_github_store_brain.py tests/roadmap/implement/test_roadmap_implement_submit.py`

## 2. Refresh brain-issue on newer own-write issue webhooks

Kind: behavior. Reads: `src/devops_cli/server/routes/webhooks.py`, `tests/server/routes/test_webhooks_brain.py`. Changes: `src/devops_cli/server/routes/webhooks.py`, `tests/server/routes/test_webhooks_brain.py`.
Adds: `_remember_own_delivery_issue`

- [x] 2.1 Add failing tests in `tests/server/routes/test_webhooks_brain.py` verifying newer App-bot `issues` deliveries refresh `brain-issue` without waking a lane while older or same-second payloads do not overwrite newer entries.
  - Verification: `$ uv run devops ci test tests/server/routes/test_webhooks_brain.py`
- [x] 2.2 Implement `_remember_own_delivery_issue` in `src/devops_cli/server/routes/webhooks.py` inside `refuse_own_write`.
  - Verification: `$ uv run devops ci test tests/server/routes/test_webhooks_brain.py`

## 3. Update cluster runbook

Kind: other. Reads: `docs/CLUSTER.md`. Changes: `docs/CLUSTER.md`.

- [x] 3.1 Update step 25 of `docs/CLUSTER.md` to document `own_write` `issues` webhook cache refreshes and `fresh=True` live reads after Jobs and Status writes.
  - Verification: `$ uv run devops ci docs`
