# Design

## Decisions

- **Logger Level**: Explicitly set `logger.setLevel(logging.INFO)` in `src/devops_cli/roadmap/job_result.py` so that `logger.isEnabledFor(logging.INFO)` is `True` regardless of the root logger level.
- **OTelLoggingHandler Filter Threshold**: Set `super().__init__(min(level, logging.INFO))` and update `setLevel()` so Python's handler dispatch in `callHandlers()` does not drop INFO records from child loggers. In `emit()`, enforce that records from `devops_cli.roadmap.job_result` pass at `INFO`, whereas records from any other logger require `self._min_level` (default `logging.WARNING`).

## Rejected alternatives

- **Set root logger to INFO**: Would cause excessive log noise across all subsystems in production.
- **Attach a dedicated OTelLoggingHandler directly to the job_result logger**: Would cause duplicate export if another handler is attached at root with `propagate=True`, and would complicate handler lifecycle management.
