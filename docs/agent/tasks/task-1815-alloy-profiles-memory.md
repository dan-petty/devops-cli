# Task: The Profiler Pod on the Busiest Node Stays Up (#1815)

**Issue**: [#1815](https://github.com/dan-petty/devops-cli/issues/1815)
**Scope**: scope/k8s
**Feasibility**: Read from the live cluster, read-only. One pod of the `alloy-profiles` DaemonSet had 31 restarts in 148 minutes, its `alloy` container's last state was `OOMKilled` (exit code 137) at the 512Mi limit, and the pod sat at 1/2 Ready in CrashLoopBackOff, while the DaemonSet's pods on the two other nodes ran without a restart. Prometheus's cAdvisor series, scraped too seldom to catch the spikes, put the pods' working sets between 197 and 351Mi, and `kubectl top` showed 205 to 215Mi on the healthy pods and 286Mi on the crashing one a few minutes after a restart.

## Description
The profiler targets every pod on its node (`profiling.ebpf.targetingScheme: all`), so its memory follows the node's pod count, and 512Mi did not hold on the node that runs the most pods. The limit is now 1024Mi and the request is unchanged at 128Mi. The values say why.

The profiler's log also shows `unsupported Go version go1.27.1 (need >= 1.13 and <= 1.26)` for the Prometheus binary: it costs that binary's profile and waits for an Alloy release whose profiler supports Go 1.27.

## Key Changes
- `k8s/monitoring/k8s-monitoring-values.yaml`: `collectors.alloy-profiles.alloy.resources.limits.memory` is `1024Mi`, with a comment on the pod count and the OOM kills.
- `tests/test_k8s_monitoring_integration.py`: `test_the_profiler_limit_leaves_room_above_the_spikes_that_killed_it` pins the request and the limit.

## Acceptance Criteria
- [x] The profiler's memory limit is 1024Mi (`test_the_profiler_limit_leaves_room_above_the_spikes_that_killed_it`).
- Pending a person: after the release reaches `main` and Argo CD syncs `k8s-monitoring`, every pod of `kubectl -n monitoring get pods -l app.kubernetes.io/name=alloy-profiles` is 2/2 Ready with no new restarts after a day. If the pod on the busiest node still reaches 1024Mi, narrow `profiling.ebpf.targetingScheme` instead of raising the limit again.
