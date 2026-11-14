# Proposal: #5738

## Why
Operators need clear, focused visibility into CLI command performance, background Roadmap Service activity, and AI/RAG operations without loading a single monolithic dashboard. Splitting `devops-cli.json` into three linked dashboards in a dedicated Grafana folder improves navigation and reduces visual complexity. Closes #5738.

## What Changes
- Split `k8s/devops/dashboards/devops-cli.json` into three focused dashboards in `k8s/devops/dashboards/`:
  1. `devops-cli.json`: Command telemetry, golden signals, breakdown by command, sub-commands, and GitHub API quotas.
  2. `roadmap-service-telemetry.json`: Roadmap Service rounds, queue depth, budget, identity refusals, webhook deliveries, alternatives check, and job success.
  3. `devops-ai-rag.json`: RAG retrieval latency, embedding cache hit rate, AI review findings breakdown, AI spend rate, and planner tools.
- Add header navigation links across all three dashboards for one-click switching.
- Add `grafana_folder: "DevOps Services"` annotation and sidecar folder configuration so dashboards load into a dedicated Grafana folder.
- Update `k8s/devops/dashboards/kustomization.yaml` and `tests/prometheus/test_k8s_monitoring_dashboards.py`.
- Update tests in `tests/grafana/test_grafana_dashboards.py`, `tests/telemetry/test_telemetry_instruments.py`, and `tests/prometheus/test_dashboard_queries.py`.
- Update living OpenSpec specifications.

## Capabilities
- `devops-cli-dashboard`: Focused dashboard for devops-cli command golden signals and execution breakdown.
- `roadmap-service-telemetry-dashboard`: Focused dashboard for Roadmap Service rounds, queues, budget, and job success.
- `ai-rag-dashboard`: Focused dashboard for AI review findings, RAG retrieval performance, and cache efficiency.

## Impact
Reduces dashboard load time and improves operator navigation through dedicated views and top-level links.

## Feasibility
All metrics and panel schemas are already validated and active. Existing panel definitions are partitioned without changing PromQL semantics.

## Existing Tool Considered
Grafana native dashboard links and sidecar folder annotations. Using standard Grafana features requires no custom code or external plugins.
