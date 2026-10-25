# Proposal: Roadmap Service Job Errors and Traceback Suppression

## Why

When roadmap jobs fail in `devops serve --service`, the service logs configuration errors with a full 1.5 KB traceback on every poll, splits runner failures across two disconnected log records (one with the cause and one with the repository), and drops git clone failures entirely (#1365). This change provides unified failure reporting with repository context and eliminates noisy configuration tracebacks.

## What Changes

This change fits into one pull request. The changes alter observable service logging and command output, so they carry a spec delta:

- **Missing configuration handling in service**: In `service_job`, catching `GitHubFileNotFoundError` when reading `.github/roadmap.toml` and re-raising a `ConfigurationError(key="service.repos", details={"path": ".github/roadmap.toml"})` stating to commit the file or remove the repository from `service.repos`.
- **Structured RoadmapRunError with ExceptionGroup**: `RoadmapRunError` aggregates each failed job's first error line (capped at 256 characters) including clone errors, attaches a PEP 654 `ExceptionGroup` as its `__cause__` with PEP 678 job notes, and provides a property `is_configuration_only` checking if all members are `ConfigurationError` instances.
- **Traceback suppression for configuration-only errors in service**: In `RepoWorker._execute_batch`, logging configuration-only failures (`ConfigurationError` or `RoadmapRunError` with only configuration errors) without `exc_info` (no traceback), while continuing to log unexpected failures with `exc_info=True`.
- **Refine visibility rate limit propagation**: In `roadmap/refine.py`, re-raising `GitHubRateLimitError` when checking repository visibility so rate-limit budget refusals propagate to the worker pause.
- **Reset calculation cleanup**: Removing `reset_at` from `RoadmapRunError` and deriving pause resets directly from `refusal_reset` across group members.
- **CLI literal formatting**: In `devops roadmap run --confirm`, printing `str(exc)` with `print_error(..., safe=True)` and exiting 1.

## Capabilities

### New Capabilities
- `roadmap-service-logs`: Roadmap service failure logging without configuration tracebacks, unified job failure messages with clone error retention, and rate limit propagation.

### Modified Capabilities
*(None)*

## Impact

- `src/devops_cli/exceptions/roadmap.py`: `RoadmapRunError` signature, properties, and removal of `reset_at`.
- `src/devops_cli/roadmap/run.py`: `_execute_due_rows`, `_prepare_clone`, `_refused_reset`, `service_pause_until`, `service_job`.
- `src/devops_cli/roadmap/refine.py`: `run_research_step` re-raising `GitHubRateLimitError`.
- `src/devops_cli/server/service.py`: `_execute_batch` error logging and span message.
- `src/devops_cli/commands/roadmap.py`: CLI error printing with `safe=True`.
- Tests in `tests/test_roadmap_run.py`, `tests/test_server_service.py`, `tests/test_roadmap_refine.py`.

## Feasibility

- **ExceptionGroup and add_note**: Tested in Python 3.14 runtime. Standard library `ExceptionGroup` and `BaseException.add_note` are available and natively formatted by `traceback` and Python `logging`.
- **Ruff and Ratchet checks**: Verified with `ruff check --select=BLE001,S110,S112` and `pytest tests/test_swallowed_failures_ratchet.py`. Unifying clone and job runner error handling in `run.py` maintains the ratchet ceiling at 5 without adding any `# noqa`.
- **No-network offline testing**: Verified that tests can use local temporary directories, mock stores, and `RepoWorker` public methods without network egress.

## Existing Tool Considered

Standard library `ExceptionGroup` (PEP 654) and `BaseException.add_note` (PEP 678) provide built-in exception aggregation and annotation. No third-party error-chaining library or ad-hoc custom group container is introduced.
