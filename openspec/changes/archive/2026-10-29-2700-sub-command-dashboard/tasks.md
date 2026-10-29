# Tasks

## 1. The sub-command labels

- [x] 1.1 Add the two label tests to `tests/test_otel_command_coverage.py` (a delegated sub-command, a command with no group), and verify that `uv run devops ci test tests/test_otel_command_coverage.py` fails on the base
- [x] 1.2 Send `command` and `sub_command` from `_subcommand_labels` in `src/devops_cli/core/cli.py`, update the two tests that call the record functions, and verify that `uv run devops ci test tests/test_otel_command_coverage.py tests/test_security_sandbox_and_protection.py tests/invariants/test_hermetic_floor.py` passes
- [x] 1.3 Run `devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. The dashboard

- [x] 2.1 Replace the test of the fixed command list in `tests/test_grafana_dashboards.py` with the tests of the query variables and the repeated panel, add the sub-command series to the chart test of `tests/test_telemetry_instruments.py`, and verify that `uv run devops ci test tests/test_grafana_dashboards.py tests/test_telemetry_instruments.py` fails on the base
- [x] 2.2 Rework `k8s/monitoring/dashboards/devops-cli.json` (the two variables, the row "Sub-commands", the row "RAG Retrieval"), and verify that `uv run devops ci test tests/test_grafana_dashboards.py tests/test_telemetry_instruments.py tests/test_k8s_monitoring_dashboards.py` passes
- [x] 2.3 Run `devops docs generate --sync-readme`, and verify that `uv run devops ci` passes

## Workflow follow-up

- The Auto grid layout with a "query has data" show/hide rule needs the v2 dashboard schema and a check that the file provider of the sidecar loads it: #2703.
- Pending a person: open the dashboard in Grafana and confirm that `sub_command` lists the sub-commands that ran in the time range.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
