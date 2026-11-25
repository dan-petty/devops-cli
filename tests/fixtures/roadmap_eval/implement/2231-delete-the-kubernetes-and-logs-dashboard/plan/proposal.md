# Proposal: #2231

## Why
The Kubernetes and Logs dashboard tabs duplicate capabilities that k9s covers. k9s is already pinned and installed. `devops dashboard` covers only what no open tool covers. Deleting both tabs removes redundant cluster queries and maintenance effort. Closes #2231.

## What Changes
Delete the Kubernetes tab and the top-level Logs tab from `devops dashboard`. Remove `K8sPanel`, `PodInspector`, and related Kubernetes projections and providers from `devops_cli.ui`. Update the default tab to Docker and adjust CLI option validation. Remove Kubernetes panel rendering from `devops dashboard --summary`.

## Capabilities
- `workstation-dashboard`: Update dashboard domains to Docker, Telemetry, and Valkey.

## Impact
`devops dashboard` starts on the Docker tab instead of Kubernetes. The `--tab` option accepts `docker`, `telemetry`, and `valkey` (numeric indexes 1, 2, 3). The command sends no queries to Kubernetes clusters during dashboard refreshes or summary runs.

## Feasibility
Verified against `src/devops_cli/ui/` and `src/devops_cli/commands/dashboard.py`. Verified that k9s is installed and pinned in `src/devops_cli/tools_lock/tools.lock`. Verified that `TelemetryPanel` uses `LogPane` and `VirtualLogBuffer`, while pod-specific log tailing belongs solely to the removed tabs.

## Existing Tool Considered
k9s version 0.51.0 covers pod inspection, pod logs, events, and container switching. `kubectl get pods` covers non-interactive pod summaries.
