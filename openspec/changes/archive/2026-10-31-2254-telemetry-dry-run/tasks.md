# Tasks

## 1. Implementation
- [x] 1.1 Create `src/devops_cli/telemetry/telemetry_plans.py` with plan generators for dashboard and telemetry commands
- [x] 1.2 Create `src/devops_cli/grafana/grafana_plans.py` with plan generators for Grafana commands
- [x] 1.3 Create `src/devops_cli/prometheus/prometheus_plans.py` with plan generators for Prometheus commands
- [x] 1.4 Update `src/devops_cli/commands/dashboard.py` to annotate `dashboard` with `@dry_run_class("request-plan")` and wire request planning under dry run
- [x] 1.5 Update `src/devops_cli/commands/grafana.py` to annotate 7 commands with `@dry_run_class("request-plan")`, annotate `dashboards lint` with `@dry_run_class("no-external-request")`, add `--dry-run` where missing, remove echo-only previews, and wire request planning
- [x] 1.6 Update `src/devops_cli/commands/prometheus.py` to annotate 5 commands with `@dry_run_class("request-plan")`, add `--dry-run` where missing, remove echo-only previews, and wire request planning
- [x] 1.7 Update `src/devops_cli/commands/telemetry.py` to annotate 5 commands with `@dry_run_class("request-plan")`, annotate `logfire` and `open-ui` with `@dry_run_class("no-external-request")`, add `--dry-run` where missing, remove echo-only previews, and wire request planning
- [x] 1.8 Remove the 21 commands from `tests/fixtures/dry_run_gaps.json`

## 2. Verification
- [x] 2.1 Add unit tests in `tests/commands/test_telemetry_monitoring_dry_run.py` verifying dry-run classifications, request plans, and zero external calls
- [x] 2.2 Update existing tests in `tests/commands/test_grafana.py` and `tests/commands/test_prometheus.py` to assert new request plan outputs
- [x] 2.3 Verify ratchet tests and full test suites pass
- [x] 2.4 Run full `devops ci` check
