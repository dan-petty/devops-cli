# Design

## Context

See `proposal.md` for motivation.
`k8s/monitoring/dcgm-exporter-values.yaml` provides values for the `nvidia-dcgm/dcgm-exporter` chart.
The chart defaults give 100m CPU / 128Mi memory request and 200m CPU / 512Mi memory limit.
The measured live RSS footprint is 420-430 MiB with 2 GPUs per node.

## Goals / Non-Goals

**Goals:**
- Provide explicit `resources` values in `k8s/monitoring/dcgm-exporter-values.yaml`.
- Prevent unexpected OOM terminations when GPU count or DCP fields increase.
- Pin dcgm-exporter's `resources` in `tests/test_k8s_monitoring_integration.py`.

**Non-Goals:**
- Adding custom Prometheus alerting rules for container memory limits.

## Decisions

### Decision 1: Explicit resource allocation in Helm values
Add a top-level `resources` mapping in `k8s/monitoring/dcgm-exporter-values.yaml`:
```yaml
# RSS about 420-430 MiB with 2 GPUs per node, 2026-10.
resources:
  requests:
    cpu: 50m
    memory: 512Mi
  limits:
    cpu: 200m
    memory: 768Mi
```
**Rationale**:
The request of 512Mi covers the baseline RSS and signals real usage to the Kubernetes scheduler.
The limit of 768Mi provides headroom for spikes or added metrics without risk of immediate OOM termination.
The CPU request of 50m matches measured CPU usage of 13-17m with safe burst allowance.

**Rejected Alternatives**:
- *Keep chart defaults*: Rejected because measured RSS (420-430 MiB) is 82-84% of the 512Mi limit.
- *Set limit to 1024Mi*: Rejected because 768Mi provides adequate headroom while limiting memory consumption on constrained nodes.

### Decision 2: Pin resources in the monitoring integration test
Verify the `resources` dictionary in `tests/test_k8s_monitoring_integration.py` within `test_dcgm_exporter_is_scraped_by_the_integration_and_holds_sys_admin`.

**Rationale**:
This test directly validates `k8s/monitoring/dcgm-exporter-values.yaml` invariants.

**Rejected Alternatives**:
- *Create a separate test file*: Rejected because `test_k8s_monitoring_integration.py` already checks `dcgm-exporter-values.yaml`.

## Risks / Trade-offs

- [Higher memory reservation] → Nodes reserve 512Mi memory per node for dcgm-exporter instead of 128Mi. The scheduler accurately places other pods without node-level memory overcommit.
