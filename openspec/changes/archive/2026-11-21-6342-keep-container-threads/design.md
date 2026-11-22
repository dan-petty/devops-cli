# Design

## Decisions
1. **Keep both thread metrics.** `container_threads` gives the thread count of a cgroup, and `container_threads_max` gives the thread limit of that cgroup. The decision on `pod-max-pids` needs the measured peak and the limit that applies now. Each metric adds one series for each cgroup.
2. **Use the list of the chart.** The entries go into `clusterMetrics.cadvisor.metricsTuning.includeMetrics`, which the chart adds to its keep rule. The default allow list of the chart stays on. Reason: this is the option of the chart for this need, and the list already holds 11 metrics for the same reason.
3. **Keep the series of each pod cgroup.** The change adds no rule that drops a thread series with an empty `container` label. Reason: the series of the pod cgroup (empty `container` and `image` labels, a `pod` label) counts each thread of the pod, as the pids cgroup does. `pod-max-pids` limits that cgroup.
4. **Read the peak from the series of the pod cgroup.** A sum over all series of a pod adds the series of the pod cgroup to the series of its sandbox and of its containers, so it counts each thread two times. The query of the peak selects `container=""`, `image=""` and `pod!=""`. The guideline names this rule, and the pull request comment gives the query to #6392.
5. **No test of the value.** Owner rule of 2026-11-16: no test reads a manifest or a configuration file and asserts a value. `helm template` of the pinned chart proves the keep rule before and after the change, and the `k8s` row of `devops ci` checks the tree. After the sync, a PromQL query proves the series.

## Rejected alternatives
- **Only `container_threads`.** Rejected: it gives the peak but not the limit that applies now.
- **`container_processes`.** Rejected: the pids cgroup counts each thread, so the process count is lower than the count that the limit uses.
- **A drop rule for the cgroups of the hosts.** The root cgroup, `kubepods` and `system.slice` give 20 of the 329 series of each metric. Rejected: a rule of the project in place of the rules of the chart, for a small decrease.
- **A separate scrape job or an exporter.** Rejected: Alloy already scrapes the cAdvisor endpoint of each node, and the series are already on it.
- **A test that reads `includeMetrics`.** Rejected by the owner rule of 2026-11-16.
