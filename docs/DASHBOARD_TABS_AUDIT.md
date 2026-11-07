# Dashboard Tabs Audit

This document audits five tabs of `devops dashboard` against open tools. The audited tabs are Kubernetes, Docker, Telemetry, Valkey and Logs.

## Method

The audit evaluates each tab against an open tool that performs the same function. The audit applies one rule: a tab stays only when no open tool covers its functions. Each section records the open tool, the functional gaps, the deleted lines, the version pin, the request cost and the person-run steps.

## Kubernetes

The open tool is k9s version 0.51.0. The file `src/devops_cli/tools_lock/tools.lock` at line 386 pins this version.

### Gap Analysis

k9s covers pods, deployments, services, nodes, events and container logs. The `K8sPanel` provides an embedded view inside `devops dashboard`. k9s does not integrate into the unified five-domain status header of `devops dashboard`. k9s covers all operational and troubleshooting features of the tab.

### Deleted Code

Replacing the Kubernetes tab deletes the following lines:
- `src/devops_cli/ui/widgets.py:379-563` (`K8sPanel`)
- `src/devops_cli/ui/data_providers.py:205-244` (`fetch_k8s_status` and `fetch_pod_events`)
- Test files `tests/ui/test_ui_k8s_provider.py`, `tests/ui/test_ui_k8s_filters.py` and `tests/ui/test_ui_k8s_stable_selection.py`

### Configuration and Pin

The pin `0.51.0` resides in `src/devops_cli/tools_lock/tools.lock`. No custom configuration file is required. The tool uses standard kubeconfig settings.

### Request Cost

The tab fetchers send two to four Kubernetes REST requests every three seconds. k9s opens streaming informers and watch connections. It sends an initial list request and then streams delta updates.

### Person-Run Steps

1. Run `k9s` against a development cluster.
2. Inspect pod statuses and view pod events.
3. Compare the interactive controls against `devops dashboard`.

## Docker

The open tool is lazydocker. No file in the repository pins lazydocker.

### Gap Analysis

lazydocker covers containers, images, volumes and container statistics. The `DockerPanel` and `fetch_docker_status` provide a container table inside `devops dashboard`. lazydocker does not integrate into the unified status bar of `devops dashboard`. lazydocker provides superior container management and log inspection.

### Deleted Code

Replacing the Docker tab deletes the following lines:
- `src/devops_cli/ui/widgets.py:564-660` (`DockerPanel`)
- `src/devops_cli/ui/data_providers.py:360-524` (`fetch_docker_status`)
- Test files `tests/ui/test_ui_docker_provider.py` and `tests/ui/test_ui_docker_inventory.py`

### Configuration and Pin

The repository does not pin lazydocker. The follow-up issue will add a binary pin to `src/devops_cli/tools_lock/tools.lock`. Default configuration connects to `/var/run/docker.sock`.

### Request Cost

The `fetch_docker_status` provider queries the local Docker socket on every refresh cycle. lazydocker queries container states via Docker API events and poll loops.

### Person-Run Steps

1. Review the lazydocker release page at `https://github.com/jesseduffield/lazydocker/releases`.
2. Start lazydocker in a terminal with active Docker containers.
3. Compare resource monitoring against `devops dashboard`.

## Telemetry

The open tool is Grafana with committed dashboards. The chart version is 14.0.1 in `k8s/argocd/apps/grafana.yaml` at line 13.

### Gap Analysis

The repository provides 15 dashboards in `k8s/monitoring/dashboards/`. The `TelemetryPanel` renders CPU and memory summaries in the terminal. Grafana dashboards cover every metric with rich graphs and query interfaces. Grafana does not render inside the terminal console.

### Deleted Code

Replacing the Telemetry tab deletes the following lines:
- `src/devops_cli/ui/widgets.py:247-378` (`TelemetryPanel`)
- `src/devops_cli/ui/data_providers.py:525-585` (`fetch_telemetry_status`)
- Test files `tests/ui/test_ui_telemetry_panel.py`, `tests/ui/test_ui_telemetry_provider.py` and `tests/ui/test_ui_telemetry_source.py`

### Configuration and Pin

Grafana is pinned at Helm chart 14.0.1 in `k8s/argocd/apps/grafana.yaml`. The values file resides at `k8s/monitoring/grafana-values.yaml`.

### Request Cost

The `fetch_telemetry_status` provider sends Prometheus queries at each refresh interval. Grafana queries Prometheus when a dashboard opens or refreshes.

### Person-Run Steps

1. Deploy the telemetry stack with `devops k8s deploy-stack --stack infra`.
2. Forward the Grafana port to localhost.
3. Open the deployed dashboards in a web browser.
4. Verify that Prometheus metrics match the terminal dashboard figures.

## Valkey

The open tool is `valkey-cli` from the `valkey-tools` package. The cluster guide cites this tool in `k8s/README.md` at line 87.

### Gap Analysis

The Valkey tab displays server version, memory usage, connected clients and hit ratios. The `valkey-cli` tool is a command-line client and provides no terminal user interface. No open terminal user interface dashboard exists for Valkey. The Valkey tab stays because no open terminal tool covers its continuous visualization.

### Deleted Code

The tab stays in `devops dashboard`. If replaced in the future, deletion would touch:
- `src/devops_cli/ui/data_providers.py:623-664` (`fetch_valkey_status`)
- `src/devops_cli/ui/projections.py:167-184` (`valkey_banner`)
- `src/devops_cli/ui/projections.py:252-269` (`valkey_rows`)
- `src/devops_cli/ui/projections.py:308-311` (`valkey_identities`)
- Test file `tests/ui/test_ui_valkey_provider.py`

### Configuration and Pin

The cluster guide references `valkey-tools` via `k8s/README.md`. Authentication uses the `VALKEY_PASSWORD` secret.

### Request Cost

The `fetch_valkey_status` provider calls `INFO` and `DBSIZE` on the Valkey endpoint at each interval. `valkey-cli` executes one command per execution.

### Person-Run Steps

1. Connect to the cluster Valkey service with `kubectl -n llm exec -it svc/valkey -c valkey -- sh -c 'VALKEYCLI_AUTH="$VALKEY_PASSWORD" valkey-cli ping'`.
2. Run `valkey-cli info` to view engine statistics.
3. Confirm that no terminal graphical interface exists for Valkey.

## Logs

The open tool is the Grafana Loki datasource. The chart version is 20.0.2 in `k8s/argocd/apps/loki.yaml` at line 13.

### Gap Analysis

`LokiLogSource` and `LogPane` provide an in-terminal log viewer with filtering. Grafana Loki Explore provides log querying, label selectors and time range filtering. Grafana does not provide an interactive terminal widget. Grafana covers all log exploration workflows.

### Deleted Code

Replacing the Logs tab deletes the following lines:
- `src/devops_cli/ui/widgets.py:200-246` (`LokiLogSource`)
- `src/devops_cli/ui/widgets.py:668-964` (`LogPane`)
- `src/devops_cli/ui/log_buffer.py:1-250`
- Test file `tests/ui/test_ui_log_pane.py`

### Configuration and Pin

Loki is pinned at chart 20.0.2 in `k8s/argocd/apps/loki.yaml`. Values are in `k8s/logging/loki-values.yaml`.

### Request Cost

`LokiLogSource` polls the Loki HTTP API every second. Grafana queries Loki on demand or streams logs with WebSocket connections.

### Person-Run Steps

1. Deploy the logging stack with `devops k8s deploy-stack --stack logging`.
2. Open Grafana Explore in a web browser.
3. Select the Loki datasource and run `{app="devops"}`.
4. Verify that log streams match the output in `LogPane`.

## Summary and Follow-up Issues

The table lists the audit decision for each tab.

| Tab | Open Tool | Verdict | Follow-up Issue Title |
| :--- | :--- | :--- | :--- |
| Kubernetes | k9s 0.51.0 | Replace | `refactor(ui): remove the k8s tab in favour of k9s` |
| Docker | lazydocker | Replace | `refactor(ui): remove the docker tab in favour of lazydocker` |
| Telemetry | Grafana (chart 14.0.1) | Replace | `refactor(ui): remove the telemetry tab in favour of Grafana` |
| Valkey | valkey-cli | Keep | None (tab stays) |
| Logs | Grafana Loki (chart 20.0.2) | Replace | `refactor(ui): remove the logs tab in favour of Grafana Loki` |

### Reason for Retaining Valkey Tab

The Valkey tab stays because no open terminal user interface covers continuous cache monitoring. `valkey-cli` is a one-shot command-line client.

### Follow-up Issue Commands

A person runs these commands after merge to file the follow-up issues:

```bash
devops gh issues create --title "refactor(ui): remove the k8s tab in favour of k9s" --body "Audit in docs/DASHBOARD_TABS_AUDIT.md (#1885) recommends removing the Kubernetes tab in favour of k9s."
```

```bash
devops gh issues create --title "refactor(ui): remove the docker tab in favour of lazydocker" --body "Audit in docs/DASHBOARD_TABS_AUDIT.md (#1885) recommends removing the Docker tab in favour of lazydocker."
```

```bash
devops gh issues create --title "refactor(ui): remove the telemetry tab in favour of Grafana" --body "Audit in docs/DASHBOARD_TABS_AUDIT.md (#1885) recommends removing the Telemetry tab in favour of Grafana dashboards."
```

```bash
devops gh issues create --title "refactor(ui): remove the logs tab in favour of Grafana Loki" --body "Audit in docs/DASHBOARD_TABS_AUDIT.md (#1885) recommends removing the Logs tab in favour of Grafana Loki."
```
