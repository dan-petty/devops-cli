# Task 135: Review Pod Restarts, Eliminate Cgroup OOM Kills & Optimize Resource Limits

**Issue**: [#135](https://github.com/dan-petty/devops-cli/issues/135)
**Status**: In Review
**Milestone**: `v0.2.16`
**Priority**: `priority/p1-high`
**Scope**: `scope/k8s`

---

## 1. Description & Root Cause Analysis

### Background & Observations
During cluster operation, multiple pods across nodes experienced terminations and restarts:
- `llm/ollama-l95dr` (on `workhorse`): 8 restarts (most recently at 18:34:36 UTC, Exit Code 255)
- `llm/ollama-z8btr` (on `condor`): 1 restart (at 18:45:32 UTC, Exit Code 255)
- `monitoring/kube-prometheus-prometheus-node-exporter-dzbwh` (on `workhorse`): 21 restarts
- `monitoring/kube-prometheus-prometheus-node-exporter-cmjhb` (on `condor`): 17 restarts
- `kube-system/nvidia-device-plugin-daemonset-jktcx` (on `workhorse`): 8 restarts
- `default/gpu-feature-discovery-57h2v` (on `workhorse`): 27 restarts

### Root Causes Identified
1. **Node Reboots & Storage Mount Failure**:
   - `workhorse` experienced emergency boot targets earlier due to a missing/faulty `/mnt/nvme-storage` filesystem entry on `/dev/sda` following hardware reconfiguration. It cleanly rebooted at 18:34:36 UTC (`uptime 5h`).
   - `condor` was rebooted at 18:45:32 UTC (`uptime 4h57m`).
   - Node reboots cause containerd to restart all running containers, explaining baseline synchronized restarts.
2. **Ollama Cgroup Memory Limit (24Gi)**:
   - `k8s/llm/ollama-daemonset.yaml` enforces `limits.memory: 24Gi`.
   - On `workhorse` (31Gi allocatable RAM), Ollama loading weights or maintaining 48k context tokens caused containerd/cgroup OOM kills (`Exit Code 255`).
   - On `condor` (64Gi allocatable RAM), the 24Gi limit artificially prevents Ollama from leveraging available physical host memory.
3. **Aggressive Liveness Probe Timeouts**:
   - Ollama's liveness probe had `timeoutSeconds: 5` and `failureThreshold: 3` with no `startupProbe`.
   - During cold start, large model downloads (70B models via Squid), or heavy KV-cache prompt processing, Ollama's HTTP server can pause or exceed 5s, triggering kubelet SIGKILL.
4. **Tight Workload Memory Limits in Supporting Services**:
   - ArgoCD controller, repoServer, server, and Redis were constrained by tight memory limits (256Mi - 1024Mi).
   - Valkey, Jaeger, Registry, and Squid exporter had tight limits risking OOM kills during burst traffic.

---

## 2. Planned Changes & Architectural Solution

1. **`k8s/llm/ollama-daemonset.yaml`**:
   - Remove `limits.memory` completely; keep `requests.cpu: 3000m` and `requests.memory: 8Gi`.
   - Add `startupProbe` with `failureThreshold: 60`, `periodSeconds: 5` (up to 5 min startup grace).
   - Relax `livenessProbe` to `timeoutSeconds: 10`, `periodSeconds: 15`, `failureThreshold: 6`.
   - Relax `readinessProbe` to `timeoutSeconds: 5`, `periodSeconds: 10`, `failureThreshold: 3`.
2. **`k8s/llm/values-ollama.yaml`**:
   - Update Helm values to match daemonset: remove limits, `requests.cpu: 1000m`, `requests.memory: 4Gi`.
3. **`k8s/llm/values-open-webui.yaml`**:
   - Raise memory limits to `4Gi` and CPU limits to `4000m`.
4. **`k8s/llm/valkey.yaml`**:
   - Raise memory limit from `512Mi` to `2048Mi`.
5. **`k8s/otel/jaeger.yaml` & `k8s/otel/values.yaml`**:
   - Raise Jaeger memory limit to `2048Mi`.
   - Raise OTel Collector memory limit to `1024Mi`.
6. **`k8s/registry/deployment.yaml`**:
   - Raise Registry memory limit to `2048Mi`.
7. **`k8s/argocd/values.yaml`**:
   - Raise controller limits to `2048Mi`, repoServer to `2048Mi`, server to `1024Mi`, redis to `1024Mi`.
8. **`k8s/squid/deployment.yaml`**:
   - Raise Squid memory limit to `16Gi` and squid-exporter limit to `256Mi`.
9. **Cluster Application**:
   - Apply updated manifests directly to the cluster (`kubectl apply`).

---

## 3. Verification & Validation Checklist
- [x] Pod restart audit completed across all namespaces.
- [x] Node boot logs and uptime inspected (5h uptime following mount repair).
- [x] Manifest updates authored and verified with unit tests (`tests/test_k8s.py`, `tests/test_k8s_valkey_stack.py`, `tests/test_k8s_jaeger.py`).
- [x] Live cluster updated via strategic patch / resource commands (`ollama`, `valkey`, `jaeger`, `registry`, `argocd`).
- [x] Ollama DaemonSet pods rolled out and verified healthy across `condor`, `workhorse`, and `hog` with version API returning `0.32.14`.
- [x] Full CI suite passing (`devops ci`).
