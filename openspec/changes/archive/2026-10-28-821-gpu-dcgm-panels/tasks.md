# Tasks

## 1. The exporter collects the counter list of its values

- [x] 1.1 Write the failing tests `test_the_exporter_reads_a_counter_list_that_asks_for_every_captured_family` and `test_a_counter_list_without_a_captured_family_fails` in `tests/test_stack_dashboards.py`, and see them fail on the `-f` argument and the missing families with `uv run devops ci test tests/test_stack_dashboards.py`
- [x] 1.2 Move the counter list into `customMetrics` of `k8s/monitoring/dcgm-exporter-values.yaml` (the image's `dcp-metrics-included.csv` plus `DCGM_FI_DEV_ENFORCED_POWER_LIMIT` and `DCGM_EXP_CLOCK_EVENTS_COUNT`), remove `arguments`, and set `podAnnotations.checksum/counters` to the SHA-256 of the list; verify with `helm template dcgm-exporter dcgm-exporter --repo https://nvidia.github.io/dcgm-exporter/helm-charts --version 4.8.4 -f k8s/monitoring/dcgm-exporter-values.yaml`, which renders the 28-field list into `exporter-metrics-config-map` and a container with no `args`
- [x] 1.3 Capture `/metrics` of the deployed exporter and of a temporary pod with the new list on each GPU card model, and add `DCGM_FI_DEV_ENFORCED_POWER_LIMIT` and `DCGM_EXP_CLOCK_EVENTS_COUNT` to `tests/fixtures/metrics/dcgm-exporter.yaml`; verify with `uv run devops ci test tests/test_stack_dashboards.py`
- [x] 1.4 Say in `k8s/README.md` where the counter list is and how the pods follow it; no command, option or message changes, so `uv run devops docs generate --sync-readme` changes nothing; verify with `uv run devops docs check`

## 2. The GPU row shows clock-event reasons, power against the enforced limit and PCIe throughput

- [x] 2.1 Write the failing tests `test_llm_stack_gpu_row_charts_clock_events_power_limit_and_pcie` and `test_the_clock_event_panel_charts_each_reason_but_idle`, and add the power panel to `LIMIT_LINES`; see them fail with `uv run devops ci test tests/test_stack_dashboards.py`
- [x] 2.2 Add the panels "GPU Power against Enforced Limit (%)", "GPU Clock Event Reasons (Samples in 5 Minutes)" and "GPU PCIe Throughput" to the GPU row of `k8s/monitoring/dashboards/llm-stack.json`, and move the Qdrant row down by one panel height; verify with `uv run devops ci test tests/test_stack_dashboards.py tests/test_grafana_dashboards.py tests/test_k8s_monitoring_integration.py tests/test_llm_pool_metrics.py`

## Fields by card

What each card model of the cluster reported on 2026-10-28 (driver 580 on the Quadro P6000, 615 on the others):

| Card | Architecture | `DCGM_FI_DEV_ENFORCED_POWER_LIMIT` | `DCGM_EXP_CLOCK_EVENTS_COUNT` | `DCGM_FI_PROF_PCIE_RX_BYTES`, `_TX_BYTES` | Does not report |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Quadro P6000 | Pascal | 175 W | yes | no | every profiling field (`DCGM_FI_PROF_*`), so no PCIe throughput |
| GeForce RTX 3090 | Ampere | 260 W | yes | no | every profiling field (`DCGM_FI_PROF_*`), so no PCIe throughput |
| Tesla PG500-216 | Volta | 150 W | yes | yes | `DCGM_FI_DEV_POWER_VIOLATION` on one GPU and `DCGM_FI_DEV_LOW_UTIL_VIOLATION` on both (a negative value, which stops the exporter's whole page) |
| GeForce RTX 5070 Ti | Blackwell | 260 W | no | yes | a named clock-event reason: it reported only bit 0x400, which the exporter does not name |

No card's SM occupancy or SM activity (`DCGM_FI_PROF_SM_OCCUPANCY`, `DCGM_FI_PROF_SM_ACTIVE`) was captured: the profiling module serves one client per GPU, and the deployed exporter is that client.

## Workflow follow-up

- #2407 adds the SM activity and occupancy panel after a capture of the profiling SM fields by the deployed exporter, in a cluster test window that a person allows.
- An allocation panel (allocatable against requested `nvidia.com/gpu`) is not built: no pod requests GPUs, because the Ollama tiers and the exporter get their GPUs through `runtimeClassName: nvidia`.
- Pending a person: after the merge, Argo CD rolls out the `dcgm-exporter` DaemonSet. Confirm that each pod is Ready and its log has no `level=ERROR`, and that the three new panels of "LLM Gateway & GPUs" show a series.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
