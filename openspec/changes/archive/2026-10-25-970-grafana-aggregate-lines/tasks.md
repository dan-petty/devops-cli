# Tasks

## 1. Test suite for aggregate lines and styling

- [x] 1.1 Update `test_dashboards_contain_properly_labeled_sum_and_average_lines` in `tests/test_grafana_dashboards.py` to assert wrapped PromQL expressions (`sum(<A>)`, `avg(<A>)`) and `byName` field overrides (`fill == 'dash'`, `lineWidth == 2`, `mode == 'fixed'`, no `axisPlacement`) across all 14 panels, and verify that `uv run pytest tests/test_grafana_dashboards.py -k properly_labeled_sum_and_average` fails on the unpatched dashboards.

## 2. Implement dashboard queries and field overrides

- [x] 2.1 Update panels in `k8s/monitoring/dashboards/sre-service.json` (7, 8), `ingress-tunnel.json` (16, 21, 22), `k8s-views-nodes.json` (26, 28), and `k8s-views-pods.json` (29, 51) to wrap refId A expressions in `sum(...)` and `avg(...)` and add dashed styling overrides with fixed colors, and verify that `uv run pytest tests/test_grafana_dashboards.py -k properly_labeled_sum_and_average` passes on these panels.
- [x] 2.2 Update panels in `k8s/monitoring/dashboards/llm-stack.json` (2, 4, 13, 14, 15) to add `Total (Sum)` and `Average (Mean)` on panel 2, wrap refId A expressions in `sum(...)` and `avg(...)` on all panels (panel 13 keeping Average only), and add dashed styling overrides with fixed colors, and verify that `uv run pytest tests/test_grafana_dashboards.py -k properly_labeled_sum_and_average` passes for all 14 panels.
- [x] 2.3 Run Grafana dashboard linting and monitoring tests to ensure dashboard schemas, PromQL queries, and ConfigMap size limits are valid, and verify that `uv run devops grafana dashboards lint k8s/monitoring/dashboards` and `uv run pytest tests/test_stack_dashboards.py tests/test_k8s_monitoring_dashboards.py` pass.

## 3. Telemetry documentation glossary

- [x] 3.1 Add a Telemetry section to `CONTEXT.md` defining *Breakdown panel* and *Aggregate line* with ASD-STE100 descriptions and `_Avoid_` lines, and verify that `grep -n "Breakdown panel\|Aggregate line" CONTEXT.md` matches both terms.
- [x] 3.2 Run documentation generator and freshness check, and verify that `uv run devops docs generate --sync-readme` and `uv run pytest tests/test_docs.py tests/test_docs_inventory.py` pass.

## Workflow follow-up

- Work on breakdown panels in `k8s-views-namespaces.json` and `k8s-views-global.json` is deferred to a future item.
- Pending a person: after merge, run `kubectl apply -k k8s/` and verify that the 14 breakdown panels in Grafana show dashed reference lines and reflect selection changes.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
