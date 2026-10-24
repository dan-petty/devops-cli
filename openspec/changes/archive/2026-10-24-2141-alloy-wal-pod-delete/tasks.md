# Tasks

## 1. The step deletes the adopted pod

- [x] 1.1 Add `kubectl -n monitoring delete pod k8s-monitoring-alloy-metrics-0` after the orphan delete in `k8s/README.md`, and say why the StatefulSet cannot replace the pod (`uv run devops ci test tests/test_k8s_monitoring_integration.py tests/test_docs.py`)
- [x] 1.2 Run the static checks (`uv run devops ci --only lint,format,docs,openspec`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
