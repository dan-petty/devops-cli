# Proposal

## Why

The node `hawk` reboots or hangs on its own, and the `alloy-profiles` DaemonSet stays off it on the suspicion that its eBPF profiler is the cause (#3785). The profiler did not run on the node for the 3 days before the hang of 2026-11-10, and that boot shows the same RCU state corruption as the boots that had the profiler, so the exclusion hides the node's profiles and prevents nothing. The hardware steps need physical access to the host, so they move to #5143.

## What Changes

- Remove the `affinity` block and its comment from the `alloy-profiles` collector of `k8s/monitoring/k8s-monitoring-values.yaml`, so the DaemonSet schedules on every node.
- Rename the collector-affinity test of `tests/commands/k8s/test_k8s_monitoring_integration.py` to `test_the_ebpf_profiler_runs_on_every_node`, and assert that no collector except `alloy-metrics` carries a `controller.affinity`.
- Run the other tests that read the collector values in the same step, because the removal reaches every assertion that names the block: `tests/ai/test_llm_pool_metrics.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_logging_stack.py`, `tests/commands/k8s/test_stack_dashboards.py`, `tests/core/test_third_party_telemetry.py`, `tests/prometheus/test_k8s_monitoring_alerting.py` and `tests/prometheus/test_k8s_monitoring_dashboards.py`.
- Delete the last sentence of the Pyroscope row of `k8s/README.md`, which states the exclusion.
- Replace the `monitoring-collectors` requirement that holds the exclusion with one that states the profiler runs on every node; `openspec archive` writes it into `openspec/specs/monitoring-collectors/spec.md`.
- Move the RAM, firmware, crash-capture and older-kernel steps to #5143, because they need physical access to the host.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `monitoring-collectors`: The alloy-profiles pod does not run on the node hawk

## Impact

- Code: `k8s/monitoring/k8s-monitoring-values.yaml`
- Documents: `k8s/README.md`
- Tests: `tests/commands/k8s/test_k8s_monitoring_integration.py`, `tests/ai/test_llm_pool_metrics.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_logging_stack.py`, `tests/commands/k8s/test_stack_dashboards.py`, `tests/core/test_third_party_telemetry.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/prometheus/test_k8s_monitoring_dashboards.py`

## Weakened checks

- **`tests/commands/k8s/test_k8s_monitoring_integration.py::test_the_ebpf_profiler_runs_on_every_node_except_hawk`**: Stopped: a change that removes the node affinity that keeps the `alloy-profiles` collector off the node `hawk`. Safeguard: The plan removes that exclusion, so group 1 renames the test to `test_the_ebpf_profiler_runs_on_every_node`. The renamed test asserts that the profiler runs on every node: no collector except `alloy-metrics` has a `controller.affinity`, and `alloy-metrics` keeps its one control-plane term.

## Feasibility

- The premise of the issue is that one node stays off the profiler through a node affinity, and the probe confirms the file: "The path `k8s/monitoring/k8s-monitoring-values.yaml` is a file of the staging commit."
- The read of `k8s/monitoring/k8s-monitoring-values.yaml` shows the exclusion under `hostPID` at `k8s/monitoring/k8s-monitoring-values.yaml:402:` `affinity:`, with the comment at `k8s/monitoring/k8s-monitoring-values.yaml:398:` `# The node hawk reboots on its own, and its kernel log of 2026-11-05 shows the eBPF map free` and the value at `k8s/monitoring/k8s-monitoring-values.yaml:410:` `- hawk`.
- The identifiers that the issue cites and that are no paths are no false premise: the probe reports "The path `seccomp.c` is no file of the staging commit. No commit in the history deleted or renamed it." and the same line for `7.2.x` and `controller.affinity`, so the issue writes them as text and no commit removed a cited file.
- The other three places that hold the exclusion are read: `k8s/README.md:319:` `shows no profile of the pods on that node`, `openspec/specs/monitoring-collectors/spec.md:23:` `### Requirement: The alloy-profiles pod does not run on the node hawk` and `tests/commands/k8s/test_k8s_monitoring_integration.py:1196:` `def test_the_ebpf_profiler_runs_on_every_node_except_hawk`.
- The test pins the exact affinity at `tests/commands/k8s/test_k8s_monitoring_integration.py:1221:` `["hawk"]`, so it fails when the entry goes and changes in the same group.
- `references` for `hawk` finds 36 lines in 12 files; outside `openspec/changes/archive/` they are `k8s/monitoring/k8s-monitoring-values.yaml`, `k8s/README.md`, `tests/commands/k8s/test_k8s_monitoring_integration.py`, `openspec/specs/monitoring-collectors/spec.md` and `CHANGELOG.md`, and each one is in a group or in a decision.
- The check of this run found that the group which changes the values file left out seven tests that read it. Each of them is now in the `changes` of that group: `tests/ai/test_llm_pool_metrics.py`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_logging_stack.py`, `tests/commands/k8s/test_stack_dashboards.py`, `tests/core/test_third_party_telemetry.py`, `tests/prometheus/test_k8s_monitoring_alerting.py` and `tests/prometheus/test_k8s_monitoring_dashboards.py`.
- The set of collectors is counted from the file: `k8s/monitoring/k8s-monitoring-values.yaml:314:` `collectors:` starts a block of 4 entries, where `alloy-metrics` keeps its control-plane term and `alloy-singleton`, `alloy-logs` and `alloy-profiles` carry no affinity, so each member is decided; the test of the first group compares the 3 others by an exact dict, so a fifth collector fails it.
- The issue body states that the profiler is not the cause: "The profiler did not run on `hawk` for 3 days before the hang, and that boot shows the same RCU state corruption as the boots that had the profiler, so the profiler is not the cause." The refine block of the same body moves the hardware investigation to its own issue.
- `read_issue` for #5143 shows an open issue titled `fix(k8s): test the hawk hardware and record the cause of its crashes`, so the host steps have a home and this plan carries no code that compensates for them.
- The plan calls no function whose arguments need a checkout, a client or a network: it edits a values file, a Markdown row and tests.
- The plan introduces no command and no verify program: `uv run devops ci test` and `uv run devops ci docs` are rows of the gate in the runner image, their failure classes are `test` and `lint`, and the pod settings stay as they are (readOnlyRootFilesystem true, runAsNonRoot true, allowPrivilegeEscalation false, seccompProfile RuntimeDefault).
- The first checks that the implementation runs against the real system are `uv run devops ci test tests/commands/k8s/test_k8s_monitoring_integration.py` and `uv run devops ci docs`; both need a checkout of the repository and no network.

## Existing Tool Considered

memtest86plus/memtest86plus covers the RAM test that the host steps need: the alternatives check of 2026-11-08 on the issue names it as open, GPL-2.0 and maintained. The Linux kernel's pstore, netconsole and kdump cover the kernel log across a reset. This change builds no code: it edits Helm values, a README row and tests, so it adopts no tool and has no build cost.

## Dependencies

None.
