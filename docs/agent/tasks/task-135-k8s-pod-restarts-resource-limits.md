# Task 135: Review Pod Restarts, Eliminate Cgroup OOM Kills & Optimize Resource Limits

**Issue**: [#135](https://github.com/dan-petty/devops-cli/issues/135)
**PR**: [#136](https://github.com/dan-petty/devops-cli/pull/136) / [#143](https://github.com/dan-petty/devops-cli/pull/143)
**Status**: Done
**Milestone**: `v0.2.16`
**Priority**: `priority/p1-high`
**Scope**: `scope/k8s`

---

## 1. Description & Root Cause Analysis

### Background & Observations
During cluster operation, multiple pods across nodes experienced terminations and restarts:
- `llm/ollama-<id>`: Restarts observed under heavy model load (Exit Code 255)
- `monitoring/kube-prometheus-prometheus-node-exporter-<id>`: Restarts observed during node initialization
- `kube-system/nvidia-device-plugin-daemonset-<id>`: Restarts observed during device re-discovery
- `default/gpu-feature-discovery-<id>`: Restarts observed under memory constraints

### Root Causes Identified
1. **Node Reboots & Storage Mount Initialization**:
   - Worker nodes experienced unscheduled host reboots following storage volume reconfiguration.
   - Host reboots trigger container runtime restart events across all daemonset workloads.
2. **Ollama Cgroup Memory Limit (24Gi)**:
   - `k8s/llm/ollama-daemonset.yaml` enforces `limits.memory: 24Gi`.
   - On standard GPU worker nodes (31Gi allocatable RAM), Ollama loading weights or maintaining large context tokens caused cgroup OOM kills (`Exit Code 255`).
   - On high-capacity worker nodes (64Gi allocatable RAM), the static 24Gi limit prevented Ollama from leveraging available physical host memory.
3. **Aggressive Liveness Probe Timeouts**:
   - Ollama's liveness probe had `timeoutSeconds: 5` and `failureThreshold: 3` with no `startupProbe`.
   - During cold start, large model downloads (70B models via Squid), or heavy KV-cache prompt processing, Ollama's HTTP server can pause or exceed 5s, triggering kubelet SIGKILL.
4. **Tight Workload Memory Limits in Supporting Services**:
   - ArgoCD controller, repoServer, server, and Redis were constrained by tight memory limits (256Mi - 1024Mi).
   - Valkey, Jaeger, Registry, and Squid exporter had tight limits risking OOM kills during burst traffic.

---

## 2. Planned Changes & Architectural Solution

1. **`k8s/llm/ollama-daemonset.yaml`**:
   - Configure bounded `limits.memory: 26Gi` (leaving sufficient node headroom for OS, kubelet, and system daemons to avoid node-level OOM), with `requests.cpu: 3000m` and `requests.memory: 8Gi`.
   - Add `startupProbe` with `failureThreshold: 60`, `periodSeconds: 5` (up to 5 min startup grace).
   - Relax `livenessProbe` to `timeoutSeconds: 10`, `periodSeconds: 15`, `failureThreshold: 6`.
   - Relax `readinessProbe` to `timeoutSeconds: 5`, `periodSeconds: 10`, `failureThreshold: 3`.
2. **`k8s/llm/values-ollama.yaml`**:
   - Update Helm values to match daemonset: `requests.cpu: 1000m`, `requests.memory: 4Gi`, `limits.memory: 26Gi`.
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
8. **`k8s/monitoring/prometheus-values.yaml`**:
   - Prometheus: Elevate `requests.memory: 1024Mi`, set `limits.memory: 4096Mi`, and unthrottle CPU limits.
   - Node Exporter: Elevate to Burstable QoS with `requests: {cpu: 50m, memory: 64Mi}` and `limits: {cpu: 200m, memory: 256Mi}`.
   - Grafana: Elevate `requests.memory: 768Mi`, `limits.memory: 2048Mi`.
   - Kube-State-Metrics: Elevate `limits: {cpu: 200m, memory: 256Mi}`.
9. **`k8s/gpu-feature-discovery/daemonset.yaml`**:
   - Elevate GPU Feature Discovery DaemonSet from `BestEffort` to `Burstable` QoS with `requests: {cpu: 50m, memory: 64Mi}` and `limits: {cpu: 200m, memory: 256Mi}` to eliminate kernel OOM kills.
10. **Cluster Application**:
    - Apply updated manifests directly to the cluster (`kubectl patch`).

---

## 3. Verification & Validation Checklist
- [x] Pod restart audit completed across all namespaces.
- [x] Node boot logs and uptime inspected.
- [x] Manifest updates authored and verified with unit tests (`tests/test_k8s.py`, `tests/test_k8s_valkey_stack.py`, `tests/test_k8s_jaeger.py`).
- [x] Live cluster updated via strategic patch / resource commands (`ollama`, `valkey`, `jaeger`, `registry`, `argocd`, `gpu-feature-discovery`, `prometheus`, `node-exporter`, `grafana`, `kube-state-metrics`).
- [x] Ollama DaemonSet pods rolled out and verified healthy across all worker nodes with version API returning `0.32.14`.
- [x] GPU Feature Discovery DaemonSet pods verified Running with Burstable QoS and 0 restarts across all cluster nodes.
- [x] Prometheus stack pods (Prometheus StatefulSet, Node Exporter DaemonSet, Grafana, Kube-State-Metrics) verified Running with Burstable QoS and 0 restarts.
- [x] Full CI suite passing (`devops ci`).
