# Proposal: #6342

## Why
Closes #6342. Prometheus has no thread series for a container or a pod, so nobody can measure the peak thread count of one runner pod. dan-petty/homelab#44 needs that peak to set the kubelet setting `pod-max-pids`. A limit that is too low can stop a runner step. The pids cgroup counts each thread, so the measure is `container_threads`, not `container_processes`. The cAdvisor endpoint of the kubelet serves the series, but the `cadvisor` keep rule of the `alloy-metrics` collector drops them.

## What Changes
- `clusterMetrics.cadvisor.metricsTuning.includeMetrics` in `k8s/monitoring/k8s-monitoring-values.yaml` gets `container_threads` and `container_threads_max`. The chart adds each entry of this list to its keep rule, after its default allow list.
- The Process IDs rule of `docs/guidelines/kubernetes.md` names the series that gives the thread count of a pod, and the series that counts each thread two times.
- The `monitoring-collectors` spec gets a requirement for the two series.

## Capabilities
- `monitoring-collectors`: ADDED requirement "Alloy keeps the cAdvisor thread series".

## Impact
- Prometheus gets about 658 new series: 329 for each of the two metrics. The cAdvisor endpoints of the 4 nodes whose cAdvisor target was up served 329 `container_threads` series on 2026-11-21: 113 containers, 98 pod sandboxes, 98 pod cgroups and 20 cgroups of the hosts. Prometheus held 64,476 head series, so the increase is about 1 %.
- Each pod adds one series for its pod cgroup, one for its sandbox and one for each container, for each metric, while it runs. A runner pod adds its series only for its run.
- The live `k8s-monitoring` Application reads the values file from `main` of this repository, so Argo CD syncs the change after the merge.
- dan-petty/homelab copies the values file with `make k8s-parity`. This change does not change homelab.
- #6392 reads the peak thread count of a runner pod 7 days after the sync.

## Feasibility
- Values: `clusterMetrics.cadvisor.metricsTuning.includeMetrics` at `k8s/monitoring/k8s-monitoring-values.yaml:43` on origin/main `671f24192` lists 11 metrics and no thread metric. The `k8s-monitoring` Application pins the chart at 4.6.1.
- Render: `helm template` of chart 4.6.1 with these values gives one `keep` rule in `prometheus.relabel "cadvisor"`. Its regex holds the default allow list of the chart and the 11 listed metrics, and no `container_threads`.
- Chart rules: the rules that drop a series with an empty `container` or `image` label match only `container_cpu_`, `container_fs_`, `container_memory_`, `container_network_` and `container_pressure_`. So the thread metrics keep the series of each pod cgroup.
- Kubelet: `kubectl get --raw /api/v1/nodes/<node>/proxy/metrics/cadvisor` lists `container_threads` and `container_threads_max` on each node whose cAdvisor target is up. The series of a pod cgroup (empty `container` and `image` labels) gives the sum of the threads of its sandbox and of its containers.
- Prometheus: `count(container_threads)` gives no result on 2026-11-21, and `count(container_memory_working_set_bytes)` gives 113.

## Existing Tool Considered
- google/cadvisor, in the kubelet, already serves `container_threads` and `container_threads_max`, and Grafana Alloy of the `k8s-monitoring` chart already scrapes it. The alternatives check of 2026-11-19 gives the verdict `in-use`.
- The chart option `metricsTuning.includeMetrics` adds a metric to the keep rule. The change adds two entries to that list. It adds no tool and no code.
