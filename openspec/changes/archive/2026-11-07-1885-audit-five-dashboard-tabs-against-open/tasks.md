# Tasks

## 1. Create the audit page with the method and the Kubernetes section

Reads: `src/devops_cli/ui/dashboard.py`, `src/devops_cli/ui/widgets.py`, `src/devops_cli/ui/data_providers.py`, `tests/ui/test_ui_k8s_provider.py`, `src/devops_cli/tools_lock/tools.lock`. Changes: `docs/DASHBOARD_TABS_AUDIT.md` (new).

- [x] 1.1 Create `docs/DASHBOARD_TABS_AUDIT.md`. State the method: one section for each of the five tabs, and each section compares the tab with the open tool that does the same job. State the rule: a tab stays only when no open tool covers one of its functions. Add the Kubernetes section. Name k9s 0.51.0 and cite the tools lock for the pin. State each function of `K8sPanel` and of `fetch_k8s_status` and `fetch_pod_events` that k9s does not cover. State the lines a replacement deletes as file and line ranges. State the pin, the config to ship, the cluster request cost that the fetchers make at the refresh interval, and the person-run steps that confirm the k9s cost on a cluster
  - Verification: `$ uv run devops ci docs` passes
- [x] 1.2 Write `docs/DASHBOARD_TABS_AUDIT.md` with the method, the rule and the Kubernetes section
  - Verification: `$ uv run devops ci docs` passes

## 2. Link the audit page from the documentation lists

Reads: `docs/DASHBOARD_TABS_AUDIT.md`, `README.md`, `docs/index.md`, `tests/invariants/test_agents_md_claims.py`. Changes: `README.md`, `docs/index.md`.

- [x] 2.1 Add one bullet to the documentation list of `README.md` and one to the primary guides of `docs/index.md`. Both name `docs/DASHBOARD_TABS_AUDIT.md` and link it. The link from `README.md` puts the page within two links of the agent router, which the two-link test requires
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md_claims.py` passes
- [x] 2.2 Edit `README.md` and `docs/index.md` with the link to the audit page
  - Verification: `$ uv run devops ci docs` passes

## 3. Add the Docker section

Reads: `src/devops_cli/ui/widgets.py`, `src/devops_cli/ui/data_providers.py`, `tests/ui/test_ui_docker_provider.py`, `tests/ui/test_ui_docker_inventory.py`, `docs/DASHBOARD_TABS_AUDIT.md`. Changes: `docs/DASHBOARD_TABS_AUDIT.md`.

- [x] 3.1 Add the Docker section. Name lazydocker as the open terminal tool that the audit tests, and state that no file of the repository pins it. State each function of `DockerPanel` in `src/devops_cli/ui/widgets.py` and of `fetch_docker_status` in `src/devops_cli/ui/data_providers.py` that lazydocker does not cover. State the lines a replacement deletes as file and line ranges in `src/devops_cli/ui/widgets.py` and `src/devops_cli/ui/data_providers.py`. State the pin and the config that the follow-up issue ships, the Docker request cost that `fetch_docker_status` makes at the refresh interval, and the person-run steps that read the lazydocker release page and compare the views
  - Verification: `$ uv run devops ci docs` passes
- [x] 3.2 Edit `docs/DASHBOARD_TABS_AUDIT.md` with the Docker section
  - Verification: `$ uv run devops ci docs` passes

## 4. Add the Telemetry section

Reads: `src/devops_cli/ui/widgets.py`, `src/devops_cli/ui/data_providers.py`, `tests/ui/test_ui_telemetry_panel.py`, `tests/ui/test_ui_telemetry_provider.py`, `tests/ui/test_ui_telemetry_source.py`, `k8s/monitoring/dashboards/kustomization.yaml`, `k8s/monitoring/grafana-values.yaml`, `k8s/argocd/apps/grafana.yaml`, `docs/DASHBOARD_TABS_AUDIT.md`. Changes: `docs/DASHBOARD_TABS_AUDIT.md`.

- [x] 4.1 Add the Telemetry section. Name Grafana at chart 14.0.1 with the dashboards that `k8s/monitoring/dashboards/kustomization.yaml` loads. Compare each panel of `TelemetryPanel` with the dashboard that holds the same metric. State each function that no dashboard covers. State the lines a replacement deletes as file and line ranges. State the Grafana pin, the config to ship, the Prometheus request cost that `fetch_telemetry_status` makes at the refresh interval, and the person-run steps
  - Verification: `$ uv run devops ci docs` passes
- [x] 4.2 Edit `docs/DASHBOARD_TABS_AUDIT.md` with the Telemetry section
  - Verification: `$ uv run devops ci docs` passes

## 5. Add the Valkey section

Reads: `src/devops_cli/ui/data_providers.py`, `src/devops_cli/ui/widgets.py`, `tests/ui/test_ui_valkey_provider.py`, `k8s/README.md`, `src/devops_cli/ai/knowledge_base/it_domains/tools/valkey.md`, `docs/DASHBOARD_TABS_AUDIT.md`. Changes: `docs/DASHBOARD_TABS_AUDIT.md`.

- [x] 5.1 Add the Valkey section. Name `valkey-cli` from the `valkey-tools` package and cite `k8s/README.md` for the check that the cluster guide gives. State each function of `fetch_valkey_status` that `valkey-cli` does not cover. State the lines a replacement deletes as file and line ranges. State the package pin and the config to ship, the Valkey request cost that `fetch_valkey_status` makes at the refresh interval, and the person-run steps. State the reason the tab stays when the audit finds no terminal user interface for it
  - Verification: `$ uv run devops ci docs` passes
- [x] 5.2 Edit `docs/DASHBOARD_TABS_AUDIT.md` with the Valkey section
  - Verification: `$ uv run devops ci docs` passes

## 6. Add the Logs section

Reads: `src/devops_cli/ui/widgets.py`, `src/devops_cli/ui/log_buffer.py`, `src/devops_cli/ui/refresh.py`, `tests/ui/test_ui_log_pane.py`, `k8s/logging/loki-values.yaml`, `k8s/argocd/apps/loki.yaml`, `docs/DASHBOARD_TABS_AUDIT.md`. Changes: `docs/DASHBOARD_TABS_AUDIT.md`.

- [x] 6.1 Add the Logs section. Name the Grafana Loki datasource, with the chart pin of `k8s/argocd/apps/loki.yaml` and the values of `k8s/logging/loki-values.yaml`. Compare `LokiLogSource` and `LogPane` with the Grafana Explore view. State each function that Grafana does not cover. State the lines a replacement deletes as file and line ranges. State the pin, the config to ship, the Loki request cost from the poll interval, and the person-run steps
  - Verification: `$ uv run devops ci docs` passes
- [x] 6.2 Edit `docs/DASHBOARD_TABS_AUDIT.md` with the Logs section
  - Verification: `$ uv run devops ci docs` passes

## 7. Add the summary table and the follow-up issues

Reads: `src/devops_cli/ui/dashboard.py`, `docs/DASHBOARD_TABS_AUDIT.md`. Changes: `docs/DASHBOARD_TABS_AUDIT.md`.

- [x] 7.1 Add a summary table to `docs/DASHBOARD_TABS_AUDIT.md` for each tab of `src/devops_cli/ui/dashboard.py`: one row for each tab, with the open tool, the verdict and the title of its follow-up issue. Add the follow-up section. Give each tab that an open tool can replace its issue title, its body that links #1885, and the `devops gh issues create` command that a person runs. State the reason for each tab that stays. Name only a command that `devops` holds, because `devops ci docs` resolves each one
  - Verification: `$ uv run devops ci docs` passes
- [x] 7.2 Edit `docs/DASHBOARD_TABS_AUDIT.md` with the summary table and the follow-up section
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 6: The task file has one section for each of the five tabs with the evidence.
- Pending person: Each tab that an open tool can replace has a follow-up issue., The audit drafts each issue's title, body and command, and a person files it with `devops gh issues create` after the merge: a rerun of a group would file a second issue, and no offline check can confirm that GitHub holds the first.
- Group 7: Each tab that stays has a written reason.
