# Proposal

## Why

Issue #821: the GPU row of the LLM stack dashboard (`k8s/monitoring/dashboards/llm-stack.json`) shows utilisation, memory, power and temperature only. When a GPU runs slow, the dashboard does not show why: it has no clock-event (throttle) reasons, no power draw against the limit that the driver enforces, and no PCIe throughput. The NVIDIA DCGM dashboard in the repository shows none of them either.

The exporter reads the counter file of its image (`-f /etc/dcgm-exporter/dcp-metrics-included.csv` in `k8s/monitoring/dcgm-exporter-values.yaml`). That file does not ask for the enforced power limit or for the clock events, and the repository holds no counter list of its own.

## What Changes

- `k8s/monitoring/dcgm-exporter-values.yaml` holds the exporter's counter list as `customMetrics`, the chart's own key. The chart writes it to its ConfigMap `exporter-metrics-config-map` and mounts it at `/etc/dcgm-exporter/default-counters.csv`, the file that the exporter reads when no `-f` is given, so the `-f` argument goes. The list is the active lines of the image's `dcp-metrics-included.csv` (4.8.4) with two more fields: `DCGM_FI_DEV_ENFORCED_POWER_LIMIT` and `DCGM_EXP_CLOCK_EVENTS_COUNT`.
- `podAnnotations` carries `checksum/counters`, the SHA-256 of the list. The chart mounts the list with `subPath`, so a running exporter never sees a new list. A changed checksum changes the pod template, and the pods restart on the new list.
- The GPU row of `llm-stack.json` gets three panels: "GPU Power against Enforced Limit (%)", "GPU Clock Event Reasons (Samples in 5 Minutes)" and "GPU PCIe Throughput". The Qdrant row moves down by one panel height.
- `tests/fixtures/metrics/dcgm-exporter.yaml` is captured again on 2026-10-28 and adds the two new families.
- `tests/test_stack_dashboards.py` checks the three panels, and checks that the counter list asks for every captured family with its captured type and that the checksum matches the list.
- `k8s/README.md` says where the counter list is and how the pods follow it.
- The change alters a manifest and a dashboard, so it carries spec deltas for the capabilities `dcgm-exporter` and `llm-stack-dashboard`.
- The change fits in one pull request.

Two parts of #821 are not built, for the reasons in Feasibility:

- SM occupancy. Its follow-up issue is #2407.
- GPU allocation (allocatable against requested `nvidia.com/gpu`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dcgm-exporter`: the exporter collects the counter list in its values, and its pods restart when the list changes.
- `llm-stack-dashboard`: the GPU row shows clock-event reasons, power against the enforced limit and PCIe throughput.

## Impact

- Manifest: `k8s/monitoring/dcgm-exporter-values.yaml`. Argo CD's `dcgm-exporter` Application applies it after the merge. The pod template changes (no `-f` argument, a new annotation), so the DaemonSet rolls its pods, half of them at a time (`maxUnavailable: 50%`). Each node's GPU metrics stop for the restart of its pod.
- Dashboard: `k8s/monitoring/dashboards/llm-stack.json`, applied by Argo CD's `monitoring` Application.
- Series: two new families. `DCGM_FI_DEV_ENFORCED_POWER_LIMIT` has one series per GPU. `DCGM_EXP_CLOCK_EVENTS_COUNT` has one series per GPU and active reason.
- Tests: `tests/test_stack_dashboards.py` and `tests/fixtures/metrics/dcgm-exporter.yaml`.

## Feasibility

Checked on 2026-10-28 on the cluster's four GPU card models (Quadro P6000, GeForce RTX 3090, Tesla PG500-216, GeForce RTX 5070 Ti) with the deployed image `nvcr.io/nvidia/k8s/dcgm-exporter:4.6.1-4.8.4-distroless` and chart 4.8.4, and against the dcgm-exporter source at tag `4.8.4`.

- **Captures.** `/metrics` of the deployed pod on each GPU node, read through `kubectl port-forward` (the API server proxy reached only the pod on its own node and gave 502 for the others). Then a temporary pod of the same image on each node (`DCGM_EXPORTER_KUBERNETES=false`, a label that no scrape selects, deleted afterwards), which read a test counter list from a temporary ConfigMap.
- **Power limit.** `DCGM_FI_DEV_ENFORCED_POWER_LIMIT` gave a value on every card (150 W, 175 W, 260 W).
- **Clock-event reasons.** `DCGM_EXP_CLOCK_EVENTS_COUNT` is the exporter's own decode of `DCGM_FI_DEV_CLOCKS_EVENT_REASONS` (`internal/pkg/collector/clock_events_collector.go`): one series per GPU and reason, labelled `clock_event`, counting the DCGM samples in a 5-minute window (`--clock-events-count-window-size`, default 300000 ms; `--collect-interval`, default 30000 ms). It skips DCGM's blank values. It gave series on the Quadro P6000, GeForce RTX 3090 and Tesla PG500-216. The GeForce RTX 5070 Ti reported only the reason bit 0x400 (`DCGM_FI_DEV_CLOCKS_EVENT_REASONS` = 1024), which the exporter's table of names (0x1 to 0x100) does not hold, so it has no series.
- **PCIe.** `DCGM_FI_PROF_PCIE_RX_BYTES` and `_TX_BYTES` are in the image's list and already in the capture. Only the Tesla PG500-216 and GeForce RTX 5070 Ti report them, because only these two report profiling fields. The 4.8.4 source maps the old `DCGM_FI_DEV_PCIE_TX_THROUGHPUT` and `_RX_THROUGHPUT` to these profiling fields (`retiredPCIeFieldReplacement`), so no field gives PCIe throughput on the other two cards.
- **Throttle-time counters rejected.** The `DCGM_FI_DEV_*_VIOLATION` counters measure throttle time in nanoseconds (a 40-second read on a GeForce RTX 3090 gave deltas below 40 × 10⁹). The Tesla PG500-216 returned about -3.58 × 10¹⁸ for `DCGM_FI_DEV_POWER_VIOLATION` on one GPU and for `DCGM_FI_DEV_LOW_UTIL_VIOLATION` on both. The exporter then refused to render the whole page (`metric family "DCGM_FI_DEV_POWER_VIOLATION" has negative counter sample`), so the node lost every GPU metric. `DCGM_EXP_CLOCK_EVENTS_TOTAL` printed no family until a reason starts after the exporter starts.
- **Final list.** The list of this change, without its profiling lines, rendered on all four nodes with no error after two collection intervals. The profiling lines are the same as in the deployed list.
- **SM occupancy: not captured.** `DCGM_FI_PROF_SM_ACTIVE` and `DCGM_FI_PROF_SM_OCCUPANCY` are profiling fields. The DCGM profiling module serves one client per GPU, and the deployed pod is that client. The temporary pod got no profiling field on the GeForce RTX 5070 Ti node, and on the Tesla PG500-216 node its GPU collector failed (`The third-party Profiling module returned an unrecoverable error`). The fields can only be captured by the deployed exporter, which needs a cluster test window that a person allows. No panel is built over a field that no capture shows; #2407 carries the panel.
- **GPU allocation: not built.** `kube_node_status_allocatable{resource="nvidia_com_gpu"}` has one series per GPU node. `kube_pod_container_resource_requests{resource="nvidia_com_gpu"}` has none, because no pod requests `nvidia.com/gpu`: the Ollama tiers (`k8s/llm/profiles/ollama-profiles.yaml`) and the exporter get their GPUs through `runtimeClassName: nvidia`. A panel of allocatable against requested GPUs would show a constant against an empty series. The memory panels already show how the GPUs are used.

## Existing Tool Considered

The NVIDIA dcgm-exporter and its Helm chart, already deployed, cover the need: the chart's `customMetrics` value is its documented way to set the counter list, and `DCGM_EXP_CLOCK_EVENTS_COUNT` is the exporter's own decode of the clock-event reasons, so no query decodes the bitmask. The checksum annotation is Helm's "automatically roll deployments" pattern (`checksum/config`), held in values because the chart's templates are not ours. The change builds no code and deletes no internal code. The tests are the only new code.
