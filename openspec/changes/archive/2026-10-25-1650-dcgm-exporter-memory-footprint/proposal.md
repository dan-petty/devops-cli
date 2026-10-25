# Proposal

## Why

The dcgm-exporter DaemonSet currently uses the chart default resource configuration (#1650).
The exporter's measured memory footprint uses 82% to 84% of its 512Mi memory limit and more than three times its 128Mi memory request.
An increase in GPU count or DCP metrics can cause an out-of-memory termination and silently stop GPU metric collection.

## What Changes

This change alters observable Kubernetes cluster configuration:
- Sets the dcgm-exporter memory request to 512Mi and memory limit to 768Mi in `k8s/monitoring/dcgm-exporter-values.yaml`.
- Sets the dcgm-exporter CPU request to 50m and CPU limit to 200m.
- Adds an inline comment that records the measured memory footprint.
- Pins the resource values as a structural tuple in the monitoring values integration test.

This change fits in one pull request.

## Capabilities

### New Capabilities
- `dcgm-exporter`: DaemonSet resources, security settings, and scrape configuration for the NVIDIA DCGM exporter.

### Modified Capabilities

## Impact

- `k8s/monitoring/dcgm-exporter-values.yaml` defines explicit resources.
- `tests/test_k8s_monitoring_integration.py` verifies the dcgm-exporter resource tuple.

## Feasibility

The premise was confirmed against the repository and cluster configuration.
`k8s/monitoring/dcgm-exporter-values.yaml` contains no `resources` key.
The upstream chart `nvidia-dcgm/dcgm-exporter` 4.8.4 defines defaults of 100m CPU and 128Mi memory request, and 200m CPU and 512Mi memory limit.
The measured RSS footprint is 420-430 MiB with two GPUs per node.
Setting requests to 50m CPU / 512Mi memory and limits to 200m CPU / 768Mi memory prevents unexpected OOM kills.

## Existing Tool Considered

The upstream `nvidia-dcgm/dcgm-exporter` Helm chart provides standard resource parameters.
We use the upstream chart's supported `resources` values rather than custom wrapper templates or runtime patches.
No internal code is deleted.
