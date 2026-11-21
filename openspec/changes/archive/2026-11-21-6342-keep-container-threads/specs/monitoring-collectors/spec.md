## ADDED Requirements

### Requirement: Alloy keeps the cAdvisor thread series
The `cadvisor` keep rule of the `alloy-metrics` collector SHALL keep `container_threads` and `container_threads_max`, so that Prometheus holds the thread count and the thread limit of each container, each pod sandbox and each pod cgroup. No rule of the values SHALL drop a thread series with an empty `container` label, because the series of the pod cgroup gives the thread count that the kubelet pod PID limit uses.

#### Scenario: The chart renders the keep rule
- **WHEN** `helm template` renders the `k8s-monitoring` chart at the version of the `k8s-monitoring` Application with `k8s/monitoring/k8s-monitoring-values.yaml`
- **THEN** the `keep` rule of `prometheus.relabel "cadvisor"` matches `container_threads` and `container_threads_max`

#### Scenario: Prometheus holds the series of a pod
- **WHEN** Argo CD has synced the values and one scrape interval has passed
- **THEN** `container_threads` and `container_threads_max` each have a series for each container, each pod sandbox and each pod cgroup of each running pod on each node whose cAdvisor target is up
