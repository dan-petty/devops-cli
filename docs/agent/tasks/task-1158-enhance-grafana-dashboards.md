# Task 1158: Enhance Grafana Dashboards for AI Spend, CLI Telemetry, GPUs, and SRE Services

**Issue**: [#1158](https://github.com/dan-petty/devops-cli/issues/1158)
**Status**: Done
**Milestone**: `v0.2.26`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/telemetry`, `scope/k8s`

---

## 1. Description & Objectives

This deliverable addresses observability enhancements and dashboard usability issues across Grafana monitoring dashboards, and aligns local AI spend calculations with realistic commercial models.

#### Key Deliverables:
- **AI Spend Dashboard (`k8s/monitoring/dashboards/ai-spend.json`)**:
  - Added rolling average trend lines across spend timeseries panels (`rate(...)[6h]` and `rate(...)[30m]`).
  - Restyled "Local Savings per Hour by Backend Server" to smooth individual lines with 20% semi-transparent fill (`drawStyle: "line"`, `fillOpacity: 20`, `lineInterpolation: "smooth"`).
  - Added run rate projection stat panels for 30-day, 90-day, and 1-year estimates below the top overview row.
- **DevOps CLI Telemetry Dashboard (`k8s/monitoring/dashboards/devops-cli.json`)**:
  - Added `$command` template variable dropdown populated from `label_values(devops_cli_command_total, command)` with multi-select and All option.
  - Added a repeating row of latency breakdown graphs for individual subcommands showing p50, p95, and p99 percentiles.
- **LLM Gateway & GPUs Dashboard (`k8s/monitoring/dashboards/llm-stack.json`)**:
  - Added rolling average trend lines to deployment request rates and GPU utilization graphs.
  - Added GPU memory utilization percentage timeseries panel with 90% and 95% threshold alert lines and `axisSoftMax: 100`.
- **SRE Service Performance & Logs Dashboard (`k8s/monitoring/dashboards/sre-service.json`)**:
  - Resized continuous profiling CPU and memory allocation flamegraphs from side-by-side (width 12) to full width (`w: 24`, 100% width) and stacked them vertically for improved readability.
- **SRE Ingress & Cloudflare Tunnel Dashboard (`k8s/monitoring/dashboards/ingress-tunnel.json` & `k8s/ingress/traefik-values.yaml`)**:
  - Enabled Prometheus router and service metric labels in Traefik configuration (`addRoutersLabels: true`, `addServicesLabels: true`).
  - Added "Traffic by Ingress Host / Router" timeseries panel querying `sum by (router) (rate(traefik_router_requests_total[2m]))`.
- **Default AI Reference Model Alignment**:
  - Updated `DEFAULT_AI_REFERENCE_MODEL` in `src/devops_cli/config/defaults.py`, `src/devops_cli/ai/spend/models.py`, `src/devops_cli/commands/ai_cost.py`, and `config.example.yaml` from `gpt-4o` to `gpt-4o-mini` ($0.15 / $0.60 per million tokens) to match the commercial capability range of local `qwen3.8:27b`.
- **Investigation Follow-ups**:
  - Follow up on node-exporter-full missing CPU and network metrics in #1129.
  - Follow up on devops-project-metrics empty state in #1132.

---

## 2. Acceptance Criteria Checklist

- [x] **AI Spend Projections & Trendlines**: Panels for 30-day, 90-day, and 1-year run rate projections added under the overview row; rolling average trendlines added to cost and token timeseries panels; local savings by backend styled with individual smooth lines and 20% fill.
- [x] **DevOps CLI Subcommand Latencies**: `$command` variable added to `devops-cli.json` dashboard templating; repeating row of p50/p95/p99 subcommand latency graphs implemented.
- [x] **GPU Memory Utilization & Trendlines**: GPU memory percentage panel with 90% and 95% threshold lines added to `llm-stack.json`; request and GPU utilization panels enhanced with rolling average trend lines.
- [x] **Flamegraph 100% Width**: Pyroscope continuous CPU and memory flamegraphs in `sre-service.json` expanded to full 100% width (`w: 24`) and stacked vertically.
- [x] **Ingress Traffic by Host/Router**: Traefik metrics configured with router/service labels and traffic by ingress router panel added to `ingress-tunnel.json`.
- [x] **AI Reference Model Alignment**: Default AI equivalent model aligned to `gpt-4o-mini` matching `qwen3.8:27b` commercial tier.
- [x] **Dashboard Validation & Quality Gates**: All 13 dashboards pass `devops grafana dashboards lint` with zero errors and zero warnings; unit tests pass in `tests/test_grafana_dashboards.py`, `tests/test_stack_dashboards.py`, and `tests/test_telemetry_instruments.py`.
- Pending a person: `devops grafana dashboards lint k8s/monitoring/dashboards`
- [x] **Changelog Fragment**: `changelog.d/1158.md` records all dashboard additions, flamegraph layout adjustments, and reference model updates.
