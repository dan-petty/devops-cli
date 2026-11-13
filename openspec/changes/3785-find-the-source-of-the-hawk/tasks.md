# Tasks

## 1. Remove the hawk affinity from the alloy-profiles collector

Reads: `k8s/monitoring/k8s-monitoring-values.yaml`, `tests/commands/k8s/test_k8s_monitoring_integration.py`. Changes: `k8s/monitoring/k8s-monitoring-values.yaml`, `tests/commands/k8s/test_k8s_monitoring_integration.py`, `tests/ai/test_llm_pool_metrics.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_logging_stack.py`, `tests/commands/k8s/test_stack_dashboards.py`, `tests/core/test_third_party_telemetry.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/prometheus/test_k8s_monitoring_dashboards.py`.

- [x] 1.1 Delete the `affinity` block and the four comment lines above it from the `alloy-profiles` collector of `k8s/monitoring/k8s-monitoring-values.yaml`, and keep its `presets`, its `hostPID` and its resources. Rename `test_the_ebpf_profiler_runs_on_every_node_except_hawk` to `test_the_ebpf_profiler_runs_on_every_node` in `tests/commands/k8s/test_k8s_monitoring_integration.py`, and assert that `alloy-profiles`, `alloy-logs` and `alloy-singleton` carry no `controller.affinity` and that `alloy-metrics` keeps its one control-plane term. Run the other tests that read the values file, and adjust an assertion only where it names the removed block
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_monitoring_integration.py tests/ai/test_llm_pool_metrics.py tests/commands/k8s/test_k8s.py tests/commands/k8s/test_k8s_logging_stack.py tests/commands/k8s/test_stack_dashboards.py tests/core/test_third_party_telemetry.py tests/prometheus/test_k8s_monitoring_alerting.py tests/prometheus/test_k8s_monitoring_dashboards.py` passes

## 2. Drop the exclusion from the Pyroscope row of the k8s README

Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [ ] 2.1 Delete the last sentence of the row of the dashboard table that names `pyroscope.json`, which says the DaemonSet keeps off one node, and keep the sentence that names `alloy-profiles`, the `profiling` feature and `destinations.localPyroscope`
  - Verification: `$ uv run devops ci docs` passes
- [ ] 2.2 Edit the Pyroscope row of `k8s/README.md` so that it states no node exclusion
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Pending person: Run a memory test on `hawk` (for example memtest86+ for several passes)., The test boots the host from its own medium, which needs physical access and root on the host, and #5143 holds that step.
- Pending person: Update the BIOS to the newest release for the board., A firmware update needs a person at the host and a reboot into the BIOS, and #5143 holds that step.
- Pending person: Capture a crash with pstore, kdump or netconsole, so that the kernel log survives the reboot., The capture reserves kernel memory on the host and lives in the dan-petty/homelab repository, and #5143 holds that step.
- Pending person: Try an older kernel, and note the result., An older kernel changes the boot loader of the host, which needs physical access, and #5143 holds that step.
- Pending person: Record the cause on this issue, with the evidence., A person writes the cause after the host tests of #5143, and only a person can record it on the issue.
- Group 1: Remove the `hawk` entry from the node affinity of `alloy-profiles` in `k8s/monitoring/k8s-monitoring-values.yaml`, if the profiler is not the cause (or keep it and name the cause).
