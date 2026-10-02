# Task: Project and Release Metrics Analytics & Grafana Dashboard (#926)

**Issue**: [#926](https://github.com/dan-petty/devops-cli/issues/926)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p1-high
**Scope**: scope/github

## Description
The project lacked automated visibility into software engineering velocity, release cadence, and project health metrics:
- **Release Frequency & Cadence**: Engineering teams needed tracking for release intervals (elapsed days between releases), release velocity over time, commits per release, and pull requests merged per release.
- **Squash-Merged Release PR Extraction**: Git tag commit counting needed support for squash-merged release PRs, parsing commit bullets (`* <message>`) and PR references (`(#<pr>)`) within commit message bodies.
- **CI Quality Gates & Checks Pass Rates**: Needed aggregation of GitHub Actions workflow runs, categorizing runs by workflow name and conclusion (`success` vs `failure`/`timed_out`), computing pass rate percentages.
- **Milestone & Taxonomy Tracking**: Required tracking open vs closed issues and completion rates per milestone, along with taxonomy label distribution across priority, scope, and type prefixes.
- **Dual Interface**: Provided both interactive terminal tables and scriptable JSON via CLI (`devops gh metrics`) and a dedicated Grafana dashboard (`project-metrics.json` / `devops-project-metrics`) backed by OpenTelemetry Prometheus series.

## Key Changes
1. **Telemetry Instruments**:
   - Added `PROJECT_RELEASES_TOTAL`, `PROJECT_COMMITS_TOTAL`, `PROJECT_PRS_TOTAL`, `PROJECT_CI_RUNS_TOTAL`, `PROJECT_ITEMS_TOTAL`, and `PROJECT_RELEASE_INTERVAL_DAYS` histogram (`bounds: (1.0, ..., 90.0)`) in `src/devops_cli/telemetry/instruments.py`.
2. **Metrics Analytics Engine**:
   - Implemented `src/devops_cli/github/metrics.py` with Pydantic models (`ReleaseCadenceMetric`, `WorkflowRunMetric`, `MilestoneMetric`, `LabelTaxonomyMetric`, `ProjectMetricsReport`).
   - Implemented `get_release_cadence_metrics()`, `get_ci_workflow_metrics()`, `get_milestone_metrics()`, `get_label_taxonomy_metrics()`, and `collect_project_metrics_report()`.
   - Implemented `emit_project_metrics_telemetry()` mapping report data to OpenTelemetry instruments.
   - Added rate-managed `api()` method to `GhCliClient` in `src/devops_cli/github/client.py`.
3. **CLI Command**:
   - Added `devops gh metrics` command in `src/devops_cli/commands/gh.py` with `--limit`, `--ci-limit`, `--milestone`, `--repo`, `--json`, and `--emit-telemetry` flags.
   - Designed modular Rich table renderers for release cadence, CI checks pass rates, milestone completion, and taxonomy labels.
4. **Grafana Dashboard & Provisioning**:
   - Created `k8s/monitoring/dashboards/project-metrics.json` (UID: `devops-project-metrics`, title: `Project & Engineering Velocity`).
   - Registered dashboard in `k8s/monitoring/dashboards/kustomization.yaml` under `grafana-devops-cli-dashboards`.
   - Updated `k8s/README.md` and `tests/test_k8s_monitoring_dashboards.py`.
5. **Testing & Invariant Compliance**:
   - Authored unit test suite in `tests/test_github_metrics.py`.
   - Updated telemetry dashboard invariants in `tests/test_telemetry_instruments.py`.
   - Passed `devops grafana dashboards lint` with 0 errors and 0 warnings.

## Acceptance Criteria
- [x] `devops gh metrics` outputs summary panel and rich tables for release cadence, CI pass rates, milestone completion, and taxonomy labels.
- [x] `devops gh metrics --json` produces valid JSON structured conforming to `ProjectMetricsReport`.
- [x] `devops gh metrics --emit-telemetry` emits all 6 OTLP metrics to Prometheus.
- [x] `project-metrics.json` passes `devops grafana dashboards lint` with 0 errors and 0 warnings.
- [x] Dashboard is provisioned in `grafana-devops-cli-dashboards` ConfigMap generator.
- [x] All unit and dashboard tests in `tests/test_github_metrics.py`, `tests/test_telemetry_instruments.py`, and `tests/test_k8s_monitoring_dashboards.py` pass.
- [x] `uv run devops ci` quality gates pass with 100% success.
