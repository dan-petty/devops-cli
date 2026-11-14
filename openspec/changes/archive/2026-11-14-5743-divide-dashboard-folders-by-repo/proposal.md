# Proposal: #5743

## Why
Operators monitor services across multiple repositories. Dashboard folders grouped generically do not isolate dashboards by repository.

## What Changes
- Set the folder annotation of product dashboards to `dan-petty/devops-cli`.
- Set the folder annotation of platform dashboards to `Platform`.
- Add a `$repo` dashboard variable to the Roadmap Service telemetry dashboard.

## Capabilities
- Repository isolation for Grafana dashboards.
- Platform dashboard grouping under `Platform`.
- Multi-repository filtering in the Roadmap Service dashboard.

## Impact
- Product dashboards appear under folder `dan-petty/devops-cli` in Grafana.
- Platform dashboards appear under folder `Platform` in Grafana.
- Operators can filter service metrics by repository.

## Feasibility
The Grafana dashboard sidecar supports the `folderAnnotation` configuration. The sidecar creates folders matching ConfigMap annotations.

## Existing Tool Considered
Grafana folder provisioning via Helm sidecar. We use the existing Grafana sidecar folder annotation mechanism.
