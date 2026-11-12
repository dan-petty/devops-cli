# Proposal: #4701

## Why

Issue #4701: `emit_service_status_telemetry` puts the indicator of the service in the label `indicator`, so each indicator is its own series. The panels "GitHub Published Service Status" and "Cloudflare Published Service Status" read `max(last_over_time(...[$__range]))` over a default range of 30 days, so an old `major` series wins over the newest status. The component gauge has the same defect with its label `status`.

## What Changes

- `emit_service_status_telemetry` sends `devops_cli_upstream_service_status` with the label `service` only, and `devops_cli_upstream_component_status` with `service` and `component` only. The value already holds the indicator or the component status.
- The two status panels of `project-metrics.json` read `last_over_time(devops_cli_upstream_service_status{service="<service>"}[1h])` as an instant query. They keep their value mappings. Their descriptions say that they show the last hour.
- `tests/fixtures/dashboard_queries/project-metrics.yaml` holds the promtool cases of the two panels.
- The text of the service instrument and `docs/TELEMETRY.md` drop "and indicator".

## Capabilities

- `metric-instruments`: ADDED "An upstream status gauge holds one series for each service and component".
- `project-metrics-dashboard`: MODIFIED "A gauge panel shows the latest value in the time range" (the status panels are the exception); ADDED "An upstream status panel shows the status of the last hour".

## Feasibility

- Prometheus, 2026-11-12, `time() - max_over_time(timestamp(devops_cli_upstream_service_status)[3d:1m])`: for `github` the newest sample is indicator `none`, 581 s old; the `major` series was last written 40,431 s before. For `cloudflare` the newest is `minor`, 581 s old; `major` is 80,120 s old.
- The panel query `max by (service) (last_over_time(devops_cli_upstream_service_status[30d]))` gives 2 ("Major Outage") for both services at the same moment.
- `count by (service, component) (last_over_time(devops_cli_upstream_component_status[7d])) > 1` returns 16 components with 2 to 5 series each.
- `git grep` finds no alert rule, panel or code that reads the label `indicator` or the component label `status`.
- promtool 3 keeps the metric name in the result of `last_over_time`, so the cases expect it.

## Existing Tool Considered

- No tool is needed: the change removes two labels from the existing emitter and changes two queries. The Prometheus naming guide says that each label value makes a new series, which is the cause here.
- Cost: about 150,000 tokens and 1.5 hours to build; nothing new to keep.

## Impact

- `src/devops_cli/telemetry/service_status.py`, `src/devops_cli/telemetry/instruments.py`, `docs/TELEMETRY.md`, `k8s/monitoring/dashboards/project-metrics.json`, `tests/telemetry/test_service_status.py`, `tests/fixtures/dashboard_queries/project-metrics.yaml`. The change fits one pull request.
- Argo CD applies the dashboard at the merge; the Service sends the new series after the next release image rolls. Until then the panels read the label series of the last hour, which is one series when the indicator did not change in that hour.
- The old label series stay in Prometheus until retention removes them; no panel reads them after one hour.
