# Proposal: #6411

## Why
Three image references live in Python constants that Renovate cannot see:
- `PROBE_IMAGE` in `service_probe.py`
- `DEFAULT_K8S_VOLUME_MOVE_IMAGE` in `defaults.py`
- `_BASE_IMAGE` and `_UV_IMAGE` in `implement_eval_harbor.py`

The uv copy in `implement_eval_harbor.py` has already drifted to 0.13.7 against 0.13.9.
Closes #6411.

## What Changes
- Add suspended CronJob templates `k8s/devops/service-probe.yaml` and `k8s/devops/volume-move.yaml`.
- Register both templates in `k8s/devops/kustomization.yaml`.
- Update `service_probe.py` to read image and security settings from `devops/service-probe` via `kubectl get cronjob`.
- Update `volume_move.py` and `volume_move_measure.py` to read image from `devops/volume-move` via `kubectl get cronjob`.
- Ship `src/devops_cli/roadmap/implement/harbor/Dockerfile` and read it via `importlib.resources`.
- Remove deleted constants `PROBE_IMAGE`, `DEFAULT_K8S_VOLUME_MOVE_IMAGE`, `_BASE_IMAGE`, and `_UV_IMAGE`.
- Update tests and documentation.

## Capabilities
- Read helper pod images from Kubernetes CronJob manifests instead of hardcoded constants.
- Ship harbor evaluation task Dockerfile in the package with automated Renovate updates.

## Impact
- Renovate detects image updates automatically.
- No breaking changes for external callers.

## Feasibility
- Verified manifest paths, `importlib.resources`, and `kubectl get cronjob` handling in the codebase.

## Existing Tool Considered
- Kubernetes manifest discovery with `kubectl get cronjob` and standard `importlib.resources`.
