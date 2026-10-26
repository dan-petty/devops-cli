# Tasks

## 1. Single Path Telemetry Gauges

- [x] 1.1 Write the failing invariant test in `tests/test_telemetry_instruments.py` verifying no gauge name is sent across both OTLP and scrape paths, verified with `uv run devops ci test tests/test_telemetry_instruments.py`.
- [x] 1.2 Remove `record_project_metrics_in_registry` and `record_service_status_in_registry` and their calls in `src/devops_cli/roadmap/run.py` and `src/devops_cli/commands/gh.py`, verified with `uv run devops ci test tests/test_telemetry_instruments.py`.
- [x] 1.3 Remove obsolete unit tests for deleted registry functions in `tests/test_github_metrics.py` and `tests/test_roadmap_run.py`, and synchronize documentation with `uv run devops docs generate --sync-readme`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
