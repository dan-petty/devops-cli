# Task: Monitor GitHub and Cloudflare Published Service Status & Fix Grafana Value Panels (#1235)

**Issue**: [#1235](https://github.com/dan-petty/devops-cli/issues/1235)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p2-medium
**Scope**: scope/telemetry, scope/cli, scope/k8s

## Description
Investigate and resolve ghost `"Value"` series appearing in Grafana dashboards (specifically `devops-llm-stack`/`llm-gateway-and-gpus` and `k8s-views-global`), and implement published service status monitoring for upstream platforms (GitHub and Cloudflare) across CLI commands, OpenTelemetry/Prometheus metrics instrumentation, and Grafana dashboard visualizations.

Upstream service health and active incident awareness are critical for distinguishing local cluster degradations from external upstream outages.

## Key Changes
1. **Grafana Ghost "Value" Series Remediation**:
   - Filtered `{api_base!=""}` on Litellm gateway panels in `k8s/monitoring/dashboards/llm-stack.json` (Panel 2: Request Rate by Deployment, Panel 4: LLM Gateway P95 Latency, Panel 5: Deployment Error Rate, Panel 7: Deployment Spend) to exclude unrouted samples (`{}`) that render as `"Value"` in legends.
   - Corrected legend format from `{{ node }}` / `{{ node}}` to `{{ instance }}` on Panel 54 ("CPU Utilization by instance") and Panel 73 ("Memory Utilization by instance") in `k8s/monitoring/dashboards/k8s-views-global.json`.
2. **Domain Models & Constants**:
   - Added Statuspage domain models (`StatuspagePage`, `StatuspageStatus`, `StatuspageComponent`, `StatuspageIncident`, `StatuspageSummary`) in `src/devops_cli/models/statuspage.py` with immutable fields and severity status properties.
   - Added `ServiceStatusError` in `src/devops_cli/exceptions/telemetry.py`.
   - Defined official API endpoints, timeouts, indicator/component mappings, and key components in `src/devops_cli/config/constants.py`.
3. **Telemetry & Upstream Service Status Client**:
   - Registered `devops_cli_upstream_service_status` and `devops_cli_upstream_component_status` instruments in `src/devops_cli/telemetry/instruments.py`.
   - Implemented `devops_cli.telemetry.service_status` with `fetch_github_status`, `fetch_cloudflare_status`, `fetch_all_service_statuses`, `emit_service_status_telemetry`, `record_service_status_in_registry`, and Rich terminal renderers (`render_statuspage_summary`, `format_status_badge`).
   - Integrated status collection into `devops roadmap run` metrics adapter for continuous background Prometheus metric emission.
4. **CLI Commands**:
   - Added `devops gh status` with `--json` and `--emit-telemetry` flags.
   - Added `devops cloudflare service-status` with `--json` and `--emit-telemetry` flags.
   - Added unified `devops status` with `--service all|github|cloudflare`, `--json`, and `--emit-telemetry` flags.
5. **Grafana Dashboard Additions**:
   - Added Panel 27 ("Cloudflare Service Status" Stat panel) to `k8s/monitoring/dashboards/ingress-tunnel.json` with color-mapped thresholds (`0: green` = Operational, `1: yellow` = Minor, `2: orange` = Major, `3: red` = Critical).
   - Added Row 21 ("Upstream Platform Operational Status") and Panels 22 & 23 ("GitHub Published Service Status", "Cloudflare Published Service Status") to `k8s/monitoring/dashboards/project-metrics.json`.
6. **Automated Verification & Tests**:
   - Added unit test suite in `tests/test_service_status.py` covering model parsing, HTTP fetching, error handling, telemetry emission, in-memory registry updates, and CLI commands.
   - Updated `tests/test_telemetry_instruments.py` to assert dashboard metric parity for `devops_cli_*` metric series across all dashboards.
   - Verified all Grafana dashboards pass `tests/test_grafana_dashboards.py`, `tests/test_stack_dashboards.py`, and `tests/test_k8s_monitoring_dashboards.py`.

## Acceptance Criteria
- [x] Litellm gateway panels in `llm-stack.json` filter unrouted samples (`{api_base!=""}`) preventing `"Value"` ghost series.
- [x] Node utilization panels in `k8s-views-global.json` use valid `{{ instance }}` legend placeholders.
- [x] Statuspage models and client handle GitHub and Cloudflare status JSON APIs defensively with bounded timeouts and error handling.
- [x] `devops gh status`, `devops cloudflare service-status`, and `devops status` commands provide human-readable Rich table and JSON output.
- [x] OpenTelemetry counters `devops_cli_upstream_service_status` and `devops_cli_upstream_component_status` emit correctly and update Prometheus metrics.
- [x] Ingress and project metrics Grafana dashboards include upstream status panels with mapped thresholds.
- [x] Unit test suite passes with structural tuple equality assertions.
- [x] `uv run devops ci` quality gates pass with 100% success.
