# Tasks

## 1. Behavior

- [x] 1.1 Write failing unit and command tests for `devops-cli-config` setting diffs, five `roadmap.devops-cli/` annotations, `devops-cli-config-changes` create/patch/30-day pruning, unchanged no-op, failed-apply guard, private sentinel exclusion, and `configmap_changed` WARNING telemetry log
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_configmap.py tests/commands/k8s/test_k8s.py`
- [x] 1.2 Add change-record constants, `--reason` option help, pure comparison/annotation/history/log builders in `src/devops_cli/k8s/configmap.py`, and `_apply_devops_configmap` in `src/devops_cli/commands/k8s/stack_lifecycle.py` for both native and Argo CD deploy paths
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_configmap.py tests/commands/k8s/test_k8s.py`

## 2. Documents

- [x] 2.1 Document annotations, ConfigMap `devops-cli-config-changes`, `configmap_changed` WARNING log record, and the 7-day `jq` query in `k8s/README.md` while preserving `docs/CLUSTER.md` Go-live check commands and regenerating CLI docs
  - Verification: `$ uv run devops ci docs`
