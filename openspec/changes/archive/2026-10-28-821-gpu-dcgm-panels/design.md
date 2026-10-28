# Design

## Where the counter list lives

The chart (`nvidia-dcgm/dcgm-exporter` 4.8.4) always renders the ConfigMap `exporter-metrics-config-map` and mounts its key `metrics` at `/etc/dcgm-exporter/default-counters.csv` with `subPath`. The key holds `customMetrics` when it is set, and the chart's built-in list when it is not. The exporter reads `/etc/dcgm-exporter/default-counters.csv` when no `-f` is given (`DefaultCollectorsFile` in `internal/pkg/appconfig/types.go`). Before this change the values passed `-f /etc/dcgm-exporter/dcp-metrics-included.csv`, a file inside the image, so the mounted ConfigMap was not read.

With `customMetrics` set and no `-f`, the list that the exporter collects is in the repository, and Argo CD applies it like any other value. A Helm value cannot load a separate `.csv` file, so the list is a block scalar in the values file.

The list keeps every active line of the image's `dcp-metrics-included.csv` (4.8.4), so a diff against that file shows only the two additions.

## Why the pods carry a checksum of the list

A `subPath` mount does not receive ConfigMap updates. The exporter watches its counter file, but its watcher (`internal/pkg/watcher/file.go`) reacts only to events on the file's own base name, and kubelet updates a directory mount by renaming a `..data` link. So no mount layout lets a running exporter see a new list: only a new pod reads it.

Helm's answer is a `checksum/config` annotation on the pod template. The chart's templates are not ours, so `podAnnotations.checksum/counters` holds the SHA-256 of `customMetrics`, and `tests/test_stack_dashboards.py` fails when the two disagree. A change to the list then changes the pod template, and the DaemonSet rolls its pods.

## Panels

All three are in the GPU row, use the row's legend `{{hostname}} GPU {{gpu}} ({{modelName}})`, and have a description that names the cards that do not report their fields.

- **GPU Power against Enforced Limit (%)**: `100 * max by (hostname, gpu, modelName) (DCGM_FI_DEV_POWER_USAGE) / max by (hostname, gpu, modelName) (DCGM_FI_DEV_ENFORCED_POWER_LIMIT)`. A threshold line at 100 % marks the limit, and `axisSoftMax: 100` keeps it on the axis. The panel takes the free place beside "GPU Temperature".
- **GPU Clock Event Reasons (Samples in 5 Minutes)**: `max by (hostname, gpu, modelName, clock_event) (DCGM_EXP_CLOCK_EVENTS_COUNT{clock_event!="gpu_idle"})`. `gpu_idle` is the normal state of an idle GPU and would hide the reasons that slow a busy GPU; the utilisation panel already shows idle time. With the default 30-second interval, 10 means that a reason held for the whole window.
- **GPU PCIe Throughput**: the receive and transmit bytes per second of `DCGM_FI_PROF_PCIE_RX_BYTES` and `DCGM_FI_PROF_PCIE_TX_BYTES`, unit `Bps`.

The new panels need no `Total (Sum)` or `Average (Mean)` line: the capability `dashboard-aggregate-lines` lists its panels by name, and a sum of power shares, reason counts or the bus rates of different cards says nothing.

## Rejected alternatives

- **The `DCGM_FI_DEV_*_VIOLATION` throttle-time counters.** They give the share of time throttled per cause, which is more than a count of samples. Rejected: on the Tesla PG500-216, `DCGM_FI_DEV_POWER_VIOLATION` (one GPU) and `DCGM_FI_DEV_LOW_UTIL_VIOLATION` (both GPUs) returned about -3.58 × 10¹⁸, and the exporter refused to render the whole page because a counter was negative. Declaring them as gauges renders the page, but `rate()` over a gauge with sentinel values gives garbage.
- **`DCGM_EXP_CLOCK_EVENTS_TOTAL`.** Rejected: it counts the starts of a reason after the exporter starts, and it printed no family in a 75-second capture. A panel over it is empty after each restart until a reason starts.
- **The raw bitmask `DCGM_FI_DEV_CLOCKS_EVENT_REASONS` decoded in PromQL** (`floor(x / 4) % 2` for each bit). Rejected: the exporter already decodes it into the `clock_event` label, and one query per bit is a hand-written copy of that table. The raw field would show the GeForce RTX 5070 Ti's bit 0x400, which neither the exporter nor its table names.
- **`DCGM_FI_DEV_POWER_MGMT_LIMIT`.** Rejected: it is the configured limit. The enforced limit is the one the driver holds after all limiters, which is what a power cap measures against.
- **A counter list file in the repository passed with `-f`.** Rejected: Argo CD renders the chart from values only, and a mount of a repository file needs a ConfigMap that the chart already makes from `customMetrics`.
- **Stakater Reloader to restart the pods on a ConfigMap change.** Rejected: the cluster does not run it, and one annotation that a test checks does the same for one DaemonSet.
- **A capture of the profiling SM fields with Argo CD's reconcile paused.** Not done in this change: it changes the deployed exporter on every node for some minutes, which a person allows. #2407 carries it.
- **An allocation panel over `kube_pod_container_resource_requests{resource="nvidia_com_gpu"}`.** Rejected: no pod requests GPUs, so the series is empty (Feasibility).

## Tests

`tests/test_stack_dashboards.py` reads files only:

- `test_llm_stack_gpu_row_charts_clock_events_power_limit_and_pcie` finds the three panels between the row "GPUs" and the next row, and checks the families each selects, that each family is in the capture, the unit and the description.
- `test_the_clock_event_panel_charts_each_reason_but_idle` checks the clock-event query and its grouping.
- `test_the_exporter_reads_a_counter_list_that_asks_for_every_captured_family` checks that the values pass no `arguments`, that `customMetrics` asks for every family in `tests/fixtures/metrics/dcgm-exporter.yaml` with the captured type, and that `checksum/counters` is the SHA-256 of the list. Every DCGM consumer (the dashboards, the alert rules in `k8s/monitoring/prometheus-values.yaml` and `ai/pool_load.py`) reads a family in that capture, so the list keeps them all.
- `test_a_counter_list_without_a_captured_family_fails` shows that a dropped family or a changed type is found.
- `LIMIT_LINES` adds the power panel, so `test_every_threshold_line_lies_within_the_axis` checks its 100 % line.
