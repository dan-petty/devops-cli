# Proposal

## Why

Issue #970: Grafana time-series breakdown panels show multi-series lines, but their aggregate lines do not aggregate the displayed lines. The aggregate queries recalculate over raw metrics, lack visual styling overrides, and one panel lacks aggregate lines.

## What Changes

- Wrap breakdown queries (refId A) in `sum()` and `avg()` for `Total (Sum)` and `Average (Mean)` across fourteen breakdown panels in five dashboards.
- Add `Total (Sum)` and `Average (Mean)` targets to panel 2 ("Calls in Flight per Deployment") in `k8s/monitoring/dashboards/llm-stack.json`.
- Add field overrides to each aggregate line: dashed line style, width 2, and fixed colors ("#B0B0B0" for sum and "#FFB357" for average).
- Update `test_dashboards_contain_properly_labeled_sum_and_average_lines` in `tests/test_grafana_dashboards.py` to verify expressions and styling overrides across all fourteen panels.
- Add a Telemetry section to `CONTEXT.md` defining *Breakdown panel* and *Aggregate line* with `_Avoid_` lines.
- Dashboards ship as manifests in Kubernetes ConfigMaps. Manifests are observable, so this change includes a spec delta.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `dashboard-aggregate-lines`: Reference lines and expressions for workload aggregates (sums and averages) across breakdown panels in repository Grafana dashboards.

### Modified Capabilities

None.

## Impact

- Dashboards: `k8s/monitoring/dashboards/sre-service.json`, `ingress-tunnel.json`, `k8s-views-nodes.json`, `k8s-views-pods.json`, and `llm-stack.json`.
- Tests: `tests/test_grafana_dashboards.py`.
- Documentation: `CONTEXT.md`.

## Feasibility

- **Aggregate expressions**: On the base branch, panel 7 in `sre-service.json` uses `avg(rate(container_cpu_usage_seconds_total...))` for `Average (Mean)`. Because 12 of 62 cluster pods run multiple containers, averaging raw container series produces a per-container mean rather than a per-pod mean. Wrapping refId A (`avg(sum by (pod) (...))`) correctly averages the pod series.
- **PromQL validator**: `src/devops_cli/prometheus/promql.py` accepts the wrapped aggregation expressions, such as `sum(sum by (pod) (...))` and `avg(sum by (api_base) (...))`. `devops grafana dashboards lint k8s/monitoring/dashboards` runs clean with these expressions.
- **Field overrides**: `k8s-views-pods.json` panel 29 already uses `byName` field overrides for the `limit` query. The Grafana schema accepts `byName` overrides with `custom.lineStyle.fill: "dash"`, `custom.lineWidth: 2`, and `color.mode: "fixed"`.
- **Existing test coverage**: The base test `test_dashboards_contain_properly_labeled_sum_and_average_lines` only checks legendFormat strings on eight panels. It fails to check panel 2, PromQL expressions, or styling overrides.

## Existing Tool Considered

Prometheus PromQL aggregations and Grafana visualization overrides cover this need directly. Nothing custom is built. The change modifies declarative JSON dashboards and documentation. It deletes no internal code.
