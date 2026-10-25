# Design: Roadmap Service Job Errors and Traceback Suppression

## Context

See `proposal.md` for background. The roadmap Service executes queued jobs for repositories via `RepoWorker`. Currently, errors raised during round execution lose repository context, clone errors are swallowed without being recorded, and missing configuration files trigger tracebacks on every polling loop.

## Goals / Non-Goals

**Goals:**
- Surface git clone errors alongside job runner failures in a unified `RoadmapRunError`.
- Tag job failures onto an `ExceptionGroup` cause with PEP 678 notes naming the affected jobs.
- Eliminate tracebacks when logging `ConfigurationError` and configuration-only `RoadmapRunError` in `RepoWorker._execute_batch`.
- Convert `GitHubFileNotFoundError` for `.github/roadmap.toml` to `ConfigurationError` at the `service_job` boundary without breaking CLI triage.
- Propagate `GitHubRateLimitError` from refine visibility queries so the service pauses on budget exhaustion.
- Maintain ratchet ceilings for swallowed exceptions (`tests/fixtures/swallowed_failures_ceilings.json`).

**Non-Goals:**
- Modifying `open_roadmap` or `read_roadmap_config` (which would break CLI triage expecting `GitHubFileNotFoundError`).
- Changing CLI traceback policy for other commands (#1006).
- Adding worker state to suppress repeat logs across polling cycles (each poll logs once per misconfigured repository).

## Decisions

### Decision 1: Use PEP 654 `ExceptionGroup` and PEP 678 `BaseException.add_note`
- *Rationale*: Standard library features supported natively by Python 3.14. `traceback` and `logging` render exception groups and their notes automatically.
- *Alternatives considered*: Custom composite error class. Rejected because standard library exception groups integrate seamlessly with Python exception formatting tools and logging formatters.

### Decision 2: Consolidate clone and runner error handling in `_execute_due_rows`
- *Rationale*: Ruff checks for blind exception catches (`BLE001`). When `logger.exception` is removed from `_execute_due_rows`, catching `Exception` becomes a BLE001 site unless handled carefully. Removing the `except Exception` from `_prepare_clone` and allowing the single loop handler to catch both clone errors and runner errors maintains `run.py`'s ceiling of 5 without `# noqa`.
- *Alternatives considered*: Narrowing `_prepare_clone`'s catch to `GitOperationError`, `subprocess.TimeoutExpired`, and `OSError`. Rejected because `run_subprocess` can also raise `SecurityError`, which would terminate the round abruptly and discard previously collected job errors.

### Decision 3: Direct `exc_info` selection in `_execute_batch`
- *Rationale*: `_execute_batch` logs inside its `except Exception as exc:` handler. Keeping `logger.error` directly in the handler (with `exc_info=not is_config_only`) prevents ruff from flagging the handler as a new BLE001 site.
- *Alternatives considered*: Extracting a helper function for error logging. Rejected because moving the logging call outside the `except` block turns the handler into an unlogged exception catch under BLE001.

### Decision 4: Conversion of missing roadmap configuration in `service_job`
- *Rationale*: In `service_job`, `.github/roadmap.toml` is expected because the repository is explicitly listed in `service.repos`. Wrapping the `open_roadmap` call to catch `GitHubFileNotFoundError` and raise `ConfigurationError(key="service.repos", details={"path": ".github/roadmap.toml"})` keeps `open_roadmap` unchanged for `devops gh issues triage`.
- *Alternatives considered*: Changing `read_roadmap_config` to raise `ConfigurationError`. Rejected because `devops gh issues triage` requires `GitHubFileNotFoundError` to determine that a repository has no roadmap board.

### Decision 5: Move reset tracking onto group members and remove `RoadmapRunError.reset_at`
- *Rationale*: Storing `reset_at` both on the exception and on member exceptions duplicates state. `_refused_reset` scans member exceptions for `refusal_reset`.
- *Alternatives considered*: Keeping `reset_at` parameter on `RoadmapRunError`. Rejected per design refinement to keep rate limit reset timestamps on the underlying rate limit errors.

## Risks / Trade-offs

- **[Risk] Long error messages in summary logs** → *Mitigation*: Cap each job's quoted error line at 256 characters and truncate newlines, ensuring bounded message lengths while preserving full tracebacks on the exception members.
- **[Risk] Rich markup formatting collision in terminal output** → *Mitigation*: Use `print_error(str(exc), safe=True)` in `devops roadmap run --confirm` to treat brackets and markup characters as literal text.
