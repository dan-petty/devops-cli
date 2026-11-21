# Tasks

## 1. Keep the cAdvisor thread series

Kind: other. Reads: `k8s/monitoring/k8s-monitoring-values.yaml`, `k8s/argocd/apps/k8s-monitoring.yaml`. Changes: `k8s/monitoring/k8s-monitoring-values.yaml`.

- [x] 1.1 Render the pinned chart with the values of the base, and record that the `keep` rule of `prometheus.relabel "cadvisor"` holds no thread metric
  - Verification: `$ helm template k8s-monitoring k8s-monitoring --repo https://grafana.github.io/helm-charts --version 4.6.1 -n monitoring -f k8s/monitoring/k8s-monitoring-values.yaml | grep -c 'container_threads|container_threads_max'` gives 0 on the base
- [x] 1.2 Add `container_threads` and `container_threads_max`, in this order, at the end of `clusterMetrics.cadvisor.metricsTuning.includeMetrics`, with a comment that gives the reason and names #6342
  - Verification: `$ helm template k8s-monitoring k8s-monitoring --repo https://grafana.github.io/helm-charts --version 4.6.1 -n monitoring -f k8s/monitoring/k8s-monitoring-values.yaml | grep -c 'container_threads|container_threads_max'` gives 1
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 2. Name the series of a pod in the guideline

Kind: other. Reads: `docs/guidelines/kubernetes.md`. Changes: `docs/guidelines/kubernetes.md`.

- [ ] 2.1 In the Process IDs rule of `docs/guidelines/kubernetes.md`, state that the cAdvisor series `container_threads` of the pod cgroup (empty `container` and `image` labels) gives the thread count that `podPidsLimit` limits, and that a sum over all series of a pod counts each thread two times
  - Verification: `$ uv run devops ci docs` passes

## 3. Measure the cost of the series

Kind: other. Reads: the cAdvisor endpoint of each node and Prometheus, read-only.

- [ ] 3.1 Count the `container_threads` and `container_threads_max` series on the cAdvisor endpoint of each node whose cAdvisor target is up, and give the sum in the pull request body
  - Verification: `$ kubectl get --raw /api/v1/nodes/<node>/proxy/metrics/cadvisor | grep -c '^container_threads{'` for each node

## Workflow follow-up

- After the merge and the Argo CD sync: `devops prometheus query 'count(container_threads)'` gives a series for each container, each pod sandbox and each pod cgroup.
- #6392 reads the peak thread count of a runner pod 7 days after the sync.
- dan-petty/homelab copies the values file with `make k8s-parity`.
