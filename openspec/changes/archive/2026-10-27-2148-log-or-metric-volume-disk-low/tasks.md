# Tasks

## 1. Alert Rule Update

- [x] Write failing test in `tests/test_k8s_monitoring_alerting.py` verifying `LogOrMetricVolumeDiskLow` join structure
  - Verification: `uv run devops ci test tests/test_k8s_monitoring_alerting.py`
- [x] Update `LogOrMetricVolumeDiskLow` in `k8s/monitoring/prometheus-values.yaml` to join `kube_pod_info` with `group_left (persistentvolumeclaim)`
  - Verification: `uv run devops ci test tests/test_k8s_monitoring_alerting.py tests/test_k8s.py`

## 2. Verification and Archive

- [x] Run `uv run devops ci fail-to-pass --base origin/main`
  - Verification: command reports failed on base and passes on head
- [x] Archive the change
  - Verification: `uv run devops openspec archive 2148-log-or-metric-volume-disk-low`
