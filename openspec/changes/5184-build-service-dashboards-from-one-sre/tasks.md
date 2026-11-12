# Tasks

## 1. The template of the service dashboards

Kind: behavior.

- [x] 1.1 Write the failing tests of the template: the layout, one unit, a sentence-case title and a description on each panel, at most 3 series, the burn-rate chart, the reference lines, the tile states, the variables, the log and profile rows, the colors and the build of each spec.
  - Verification: `$ uv run pytest tests/grafana/test_service_dashboard.py -q`
- [x] 1.2 Add the dependency group `dashboards` with `grafana-foundation-sdk==0.0.22`, and write `src/devops_cli/grafana/service_dashboard.py` with `ServiceSpec`, `service_dashboard`, `dashboard_text`, `load_specs`, `write_dashboards` and `main`.
  - Verification: `$ uv run pytest tests/grafana/test_service_dashboard.py -q`

## 2. The SLO cases of the query harness

Kind: behavior.

- [x] 2.1 Let a case file with the key `spec` hold the cases of the template build of that spec, and add `service-template.yaml` (1,000 requests, 2 failed, SLO 99 %: SLI 0.998, 80 % of the budget left, burn rate 0.2x) and `devops-roadmap-service.yaml`.
  - Verification: `$ uv run pytest tests/prometheus/test_dashboard_queries.py -q`

## 3. The generated dashboards

Kind: manifest.

- [x] 3.1 Add `k8s/monitoring/dashboards/services.toml` with the specs of the roadmap Service and of the generic service dashboard, add the target `dashboards` to the `Makefile`, and run it.
  - Verification: `$ uv run pytest tests/grafana/test_service_dashboard.py -q -k committed`
- [x] 3.2 Provision both dashboards in the ConfigMap `grafana-service-dashboards`, delete `sre-service.json`, and change the tests and the Loki comment that named it.
  - Verification: `$ uv run pytest tests/prometheus tests/grafana tests/commands/k8s/test_k8s.py -q`
- [x] 3.3 Run `make dashboards` in the CI job "Design Tokens" and fail it when a committed dashboard is not the build.
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`

## 4. Documents

Kind: other.

- [x] 4.1 Name the template in the row "Grafana" of docs/DESIGN.md, and update the job text of docs/DESIGN.md and docs/SDLC.md, the dashboard tables of k8s/README.md, and the harness section of docs/TESTING.md.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #5278 deletes the home-grown builders of `devops_cli.grafana.builders`.
- #4743 has the gap of the linter, which does not check the panels of a collapsed row.
- Pending a person: confirm the SLO of 99.9 % over 30 days of both specs in `services.toml`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
