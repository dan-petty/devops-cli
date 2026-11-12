# Design

## Decisions

- **Remove the exclusion instead of keeping it with the cause named.**: The profiler did not run on the node for the 3 days before the 2026-11-10 hang, and that boot shows the same RCU state corruption as the boots that had the profiler, so the profiler is not the cause that the exclusion waited for.
- **Replace the `monitoring-collectors` requirement in place, with its base name and its base scenario name.**: An OpenSpec delta replaces a living requirement by its name and refuses a modified name that the base spec does not hold, and the job restores a base scenario that a modified block omits, so the delta keeps both names and states the new behavior in the text and in the scenario result.
- **List every test that reads the collector values in the group that changes them.**: The implement job edits only a test that the group names in `changes`, so a test that reads the values file stays out of reach when an assertion names the removed block.
- **Leave `openspec/specs/monitoring-collectors/spec.md` and `CHANGELOG.md` to their writers.**: `openspec archive` writes the living spec from the spec delta, and release-please writes the changelog line from the squash commit title, so no task edits either file.
- **Keep the `alloy-metrics` control-plane affinity and assert it in the same test.**: It keeps the write-ahead log volume off the node with the least free space (#1634) and has nothing to do with the host faults, so the test pins it beside the collectors that carry none.
- **Put the host steps in #5143 and keep this change to the repository files.**: Every host step needs physical access and root on the machine, and the crash capture lives in the dan-petty/homelab repository, so no pull request of this repository delivers them.

## Rejected alternatives

- **Keep the exclusion and record that the cause is still open.**: The 2026-11-10 hang came after 3 days without the profiler and holds the same RCU state corruption, so the exclusion guards nothing, and the acceptance criterion of #3785 removes the entry when the profiler is not the cause.
- **Change the values file alone and leave the test, the README and the spec.**: `tests/commands/k8s/test_k8s_monitoring_integration.py:1221:` `["hawk"]` asserts the exact affinity, so it fails when the entry goes, and the README row and the spec requirement would state an exclusion that no manifest holds.
- **Run the RAM test and the crash capture from this repository.**: No command of the repository runs a RAM test, updates firmware or installs a kernel, and the crash capture of the node is in the dan-petty/homelab repository; #5143 holds those steps.

## Unchanged references

- `openspec/specs/monitoring-collectors/spec.md` (living spec): `openspec archive` writes the living spec from the spec delta of the change, so no group edits it.
- `CHANGELOG.md` (changelog line): release-please writes the changelog line from the squash commit title, so no group edits it.

## Security

The `alloy-profiles` DaemonSet runs as root in the host PID namespace and loads eBPF programs on a node, which is the widest privilege of the monitoring stack, and this change lets it run on the node that was kept off. Nothing new crosses a trust boundary: the pod already runs on every other node with the same `root` preset and `hostPID`, and the exclusion guarded a kernel fault, not a secret or a network path. A person must confirm that the host faults do not depend on the profiler, and the 2026-11-10 hang after 3 days without the profiler shows they do not. The test `test_the_ebpf_profiler_runs_on_every_node` in `tests/commands/k8s/test_k8s_monitoring_integration.py` fails if `alloy-profiles` gains an affinity again, or if any other collector gains one.
