# Proposal: #5184

## Why

The dashboards of `k8s/monitoring/dashboards/` are hand-written JSON, and each one applies the SRE layout and the colors of docs/DESIGN.md by hand (#5184). `sre-service.json` has no SLO row and does not show the golden signals in the order of the book. On 2026-11-12 the owner asked for one template for the dashboards of Kubernetes services that applies the SRE rules in the light and the dark theme, with the look of the start page, the docs site and the reports (#4735).

## What Changes

- `src/devops_cli/grafana/service_dashboard.py` builds the classic dashboard JSON of one service from a `ServiceSpec` with the Grafana Foundation SDK: the row of 4 SLO tiles (`w6 h4`), the burn rate (1 h against 14.4x, 6 h against 6x, the 1x pace) and the budget left of the rolling window (`w12 h8`), the golden signals in the order latency, traffic, errors, saturation (`w12 h8`), then the collapsed rows of capacity, logs and profiles. The default requests are the Traefik service metrics of the Kubernetes Service that has the name of the workload. The colors come from the token build: series 1 and 2 are the hex of `color.data.cat.1` and `color.data.cat.2`, the rest are the Grafana names `text`, `semi-dark-orange` and `red`.
- `k8s/monitoring/dashboards/services.toml` holds the specs: the roadmap Service (`devops-roadmap-service.json`) and the generic service dashboard with the variables `namespace` and `workload` (`devops-sre-service.json`), which replaces `sre-service.json`. Both use an SLO of 99.9 % over 30 days (C12), which the pull request asks the owner to confirm. `make dashboards` writes `<uid>.json` for each spec. The ConfigMap `grafana-service-dashboards` provisions them.
- The SDK is in the dev dependency group, not in the runtime dependencies.
- The CI job "Design Tokens" runs `make dashboards` and fails when a committed dashboard is not the build. Its path filter adds the template.
- The query harness of #4680 reads a case file with the key `spec` as the cases of the template build of that spec. `service-template.yaml` (SLO 99 %) and `devops-roadmap-service.yaml` hold the SLI, budget and burn-rate cases.
- docs/DESIGN.md names the template in the row "Grafana", and k8s/README.md and docs/TESTING.md tell how to change a service dashboard and how to add a case.
- A dashboard and a manifest are observable, so the change has spec deltas. It fits one pull request.

## Capabilities

### New Capabilities

- `service-dashboard-template`: the template, its layout, units, series, colors and variables, the build of the committed dashboards and its CI check.

### Modified Capabilities

- `sre-service-dashboard`: the generic service dashboard comes from the template; the Loki comment and the README entry name the new panels.
- `dashboard-aggregate-lines`: `sre-service.json` leaves the list of breakdown panels.

## Impact

- `sre-service.json` (uid `devops-sre-service`) goes. The generated `devops-sre-service.json` keeps its uid, so a link to the dashboard still opens it. The panel ids change.
- New: `devops-roadmap-service.json` (uid `devops-roadmap-service`). When #3655 merges, its jobs table goes into the template or next to this layout.
- #4728 then applies to the template: the default namespace is `devops` and the workload `roadmap-service` already; its finer Traefik buckets change the latency quantiles.
- A change to the SDK pin or to a token color changes the generated JSON, and `make dashboards` writes it again.

## Feasibility

- PyPI (2026-11-12): `grafana-foundation-sdk` 0.0.22 of 2026-10-29, Apache-2.0, no dependencies, with `py.typed`. PyPI sorts the older epoch releases (`1769699998!10.1.0`) above 0.0.22, so the pin is exact (`==0.0.22`).
- SDK source at tag `v0.0.22`: `.cog/resources/dashboard/config.yaml` reads `kinds/dashboard/dashboard_kind.cue` of Grafana v12.3.3. The kind of Grafana v13.3.1 has the same `schemaVersion: uint16 | *42` and adds only optional fields (`enableGroupBy`, `valuesFormat`, `regexApplyTo`, `properties`, the link `origin`). The build writes `"schemaVersion": 42`, `panels` and rows with `collapsed`: the classic JSON that the dashboard sidecar provisions as files.
- The SDK marks its classic `Dashboard` builder deprecated in favor of `dashboardv2`. The sidecar provisions only the classic JSON, so the template uses the classic builder and keeps that one warning out of the build.
- Live Grafana: `/api/health` gives 13.3.1. The preview copies of both dashboards saved through `/api/dashboards/db` with no error, and the image renderer drew them in the light and the dark theme with 24 h of data: each panel, the capacity, log and flame graph panels in the collapsed rows too.
- Live Prometheus: `traefik_service_requests_total{service="devops-roadmap-service-8000@kubernetes"}` counted 3,566 requests in 24 h (2,468 code 202, 1,097 code 200, 1 code 502). The Traefik series carry `namespace="kube-system"`, the namespace of Traefik, so the template selects the service by `service=~"<namespace>-<workload>-[0-9]+@kubernetes"`. `traefik_service_request_duration_seconds_bucket` has the label `code` and the buckets 0.1, 0.3, 1.2 and 5 s.
- Live Pyroscope: `service_name="roadmap-service"` in `service_namespace="devops"`; in 6 h it has `process_cpu` profiles and no `memory:inuse_space` profiles, so the roadmap spec has the CPU profiles only.
- The token build has an output that Python reads: `devops_cli.design.tokens()` reads `tokens-base.json` (`color-data-cat-1` `#a463f2`, `color-data-cat-2` `#e7298a`, `chart-stroke-data` `1.5px`, `chart-stroke-reference` `1px`). The Style Dictionary config does not change.
- promtool 3.15.1 compares the samples of a case with no tolerance (`exp: 2E-03`, `got: 1.9999999999999983E-03` fails), so the cases use counters that start at 0 in the window, which promtool does not extrapolate.

## Existing Tool Considered

- **Grafana Foundation SDK** (chosen): typed Python builders of Grafana Labs, Apache-2.0, maintained (0.0.22 on 2026-10-29).
- grafonnet: Jsonnet, so a second language and tool chain in a Python project.
- grafanalib: no release since 2024-01-12, and its owner Weaveworks closed. Not maintained.
- Grafana library panels: stored in the Grafana database, not in git, and Argo CD prunes and heals the cluster from git.
- Sloth and Pyrra: they write SLO recording and alert rules, not this layout. They are for the alerts of #3655.
- Deleted: `k8s/monitoring/dashboards/sre-service.json` (35 KB of hand-written JSON) and its structure tests in `tests/grafana/test_grafana_dashboards.py`. The home-grown builders of `devops_cli.grafana.builders`, which only tests use, stay for the linter tests; #5278 deletes them.
