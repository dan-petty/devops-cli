# Task 1267: Resolve Portkey Probe Path and GPU Feature Discovery Image Tag

**Issue**: [#1267](https://github.com/dan-petty/devops-cli/issues/1267)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: type/bug, scope/k8s

---

## 1. Description & Objectives

Investigate and remediate active Kubernetes pod restarts and deployment failures in the homelab cluster:
- **Portkey AI Gateway Health Probes**: Portkey in namespace `llm` continuously crashed into `CrashLoopBackOff` (33+ restarts). Kubelet liveness and readiness probes were querying `/health`, which Portkey answers with HTTP 404 Not Found, causing probe failures and `SIGTERM` restarts every 60 seconds. Portkey serves HTTP 200 OK at `/`.
- **GPU Feature Discovery Image Tag**: In namespace `default`, the `gpu-feature-discovery` DaemonSet failed rollout with `ImagePullBackOff` on `<gpu-node-2>` because `nvcr.io/nvidia/gpu-feature-discovery:v0.20.1` does not exist in NVIDIA NGC (0.20.1 is the Helm chart version). The image was aligned to `nvcr.io/nvidia/k8s-device-plugin:v0.16.2`, which packages `/usr/bin/gpu-feature-discovery`.
- **CLI AI Gateway Probe Routing**: Updated `_probe_gateway_http` in `src/devops_cli/ai/gateway.py` to check `/` for Portkey gateway instances.

---

## 2. Acceptance Criteria

- [x] Portkey deployment manifest `k8s/llm/portkey/deployment.yaml` updated to query `/` for liveness and readiness probes.
- [x] CLI gateway probe helper `src/devops_cli/ai/gateway.py` updated to check `/` for the Portkey provider.
- [x] GPU Feature Discovery DaemonSet `k8s/gpu-feature-discovery/daemonset.yaml` corrected to use `nvcr.io/nvidia/k8s-device-plugin:v0.16.2` and version label `0.16.2`.
- [x] Unit and integration tests updated in `tests/test_k8s.py` and passing across `tests/test_ai_gateway_portkey.py`.
- [x] Live cluster manifests applied and verified with 0 active restarts and healthy endpoints.
- [x] Changelog fragment `changelog.d/1267.md` authored.
- [x] Gated CI quality checks pass in `uv run devops ci`.
- [x] Ambient Logfire pytest plugin disabled in `pyproject.toml` to prevent background network DNS resolution during dry-run tests.

---

## 3. Deliverables

- [x] `k8s/llm/portkey/deployment.yaml`: Configured `/` probe path.
- [x] `src/devops_cli/ai/gateway.py`: Updated Portkey probe endpoint in `_probe_gateway_http`.
- [x] `k8s/gpu-feature-discovery/daemonset.yaml`: Aligned image to `nvcr.io/nvidia/k8s-device-plugin:v0.16.2`.
- [x] `tests/test_k8s.py`: Updated GFD container image assertion.
- [x] `pyproject.toml`: Disabled ambient Logfire pytest plugins (`-p no:logfire -p no:pytest_logfire`).
- [x] `changelog.d/1267.md`: Authored changelog fragment for issue #1267.
- [x] `docs/agent/tasks/task-1267-resolve-portkey-probes-and-gfd-image.md`: Documented task lifecycle.
