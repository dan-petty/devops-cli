# Tasks

## 1. Exception Group and Rate Limit Re-raise

- [x] 1.1 Write failing tests for `RoadmapRunError` (exception group cause, job notes, `is_configuration_only`, removal of `reset_at`) and refine visibility `GitHubRateLimitError` re-raise. Verify with `uv run devops ci test tests/test_roadmap_run.py tests/test_roadmap_refine.py`.
- [x] 1.2 Implement `RoadmapRunError` updates in `src/devops_cli/exceptions/roadmap.py` and rate limit re-raise in `src/devops_cli/roadmap/refine.py`. Verify with `uv run devops ci test tests/test_roadmap_run.py tests/test_roadmap_refine.py`.

## 2. Roadmap Execution Error Handling and Clone Retention

- [x] 2.1 Write failing tests in `tests/test_roadmap_run.py` for clone failure retention, unified message formatting with 256-character truncation, `service_pause_until` member scanning, and `service_job` missing `.github/roadmap.toml` conversion to `ConfigurationError`. Verify with `uv run devops ci test tests/test_roadmap_run.py`.
- [x] 2.2 Implement `_prepare_clone`, `_execute_due_rows`, `_refused_reset`, `service_pause_until`, and `service_job` in `src/devops_cli/roadmap/run.py`. Verify with `uv run devops ci test tests/test_roadmap_run.py`.

## 3. Service Worker Traceback Suppression and CLI Literal Output

- [x] 3.1 Write failing tests in `tests/test_server_service.py` for `RepoWorker._execute_batch` configuration-only traceback suppression vs unexpected error `exc_info=True`, and in `tests/test_roadmap_run.py` for `devops roadmap run --confirm` safe output. Verify with `uv run devops ci test tests/test_server_service.py tests/test_roadmap_run.py`.
- [x] 3.2 Implement traceback suppression in `src/devops_cli/server/service.py` and literal safe error printing in `src/devops_cli/commands/roadmap.py`. Verify with `uv run devops ci test tests/test_server_service.py tests/test_roadmap_run.py`.
- [x] 3.3 Regenerate documentation with `uv run devops docs generate --sync-readme` and verify with `uv run pytest tests/test_swallowed_failures_ratchet.py`.

## Workflow follow-up

- Pending a person: once the Service runs again (as D2's App or a reinstated account): verify Loki queries (a), (b), and (c).
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
