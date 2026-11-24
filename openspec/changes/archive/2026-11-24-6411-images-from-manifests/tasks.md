# Tasks

## 1. Behavior

- [x] 1.1 Add CronJob manifest templates in `k8s/devops/` and register in `kustomization.yaml`
  - Verification: `$ uv run devops ci k8s`
- [x] 1.2 Update `service_probe.py` to read template from cluster
  - Verification: `$ uv run devops ci test tests/k8s/test_service_probe.py`
- [x] 1.3 Update `volume_move.py` and `volume_move_measure.py` to read template from cluster
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_volume_move.py tests/k8s/test_k8s_volume_measure.py`
- [x] 1.4 Add shipped harbor Dockerfile and update `implement_eval_harbor.py`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_eval_harbor.py`
- [x] 1.5 Remove obsolete constants and references
  - Verification: `$ uv run devops ci lint`

## 2. Documents

- [x] 2.1 Update documentation and comments
  - Verification: `$ uv run devops ci docs`
