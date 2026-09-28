# Task 126: Minikube GPU Detection & Dynamic Service NodePort Reachability Fallback

**Issue**: [#126](https://github.com/dan-petty/devops-cli/issues/126)
**Status**: Done
**Milestone**: `v0.2.19`
**Priority**: `priority/p1-high`
**Scope**: `scope/k8s`, `scope/cli`

---

## 1. Description & Objectives

In DevContainer environments, `devops devcontainer run-lifecycle` or `devops k8s bootstrap` starts Minikube. If the host has an NVIDIA GPU passed into the container, Minikube must be launched with `--gpus=all`, falling back to standard CPU mode if GPU acceleration is unavailable. Furthermore, service NodePorts (`minikube service --url`) pointing to Minikube internal IPs (`192.0.2.2:<port>`) are often unreachable from within container network namespaces without localhost port-forwarding.

Objectives:
1. **Automated GPU Enablement**: Detect NVIDIA GPU hardware via `shutil.which("nvidia-smi")` and attempt `minikube start --driver=docker --gpus=all`, cleanly falling back to CPU mode (`minikube start --driver=docker`) on failure.
2. **Dynamic Service Reachability Verification**: Enhance `devops k8s configure-urls` with non-blocking socket reachability verification on resolved NodePort URLs.
3. **Localhost Fallback & Full Persistence**: Automatically fall back to localhost port-forwarding (`http://localhost:<nodePort>` or `tcp://localhost:<nodePort>`) and persist all resolved endpoints (`argocd.url`, `grafana.url`, `prometheus.url`, `jaeger.url`, `ai.ollama_urls`, `open_webui.url`, `qdrant.url`, `valkey.url`) into configuration when internal Minikube IPs are unreachable.
4. **Automatic URL Configuration on Bootstrap**: Ensure `devops k8s bootstrap` automatically invokes `configure_urls` after stack deployment.
5. **Comprehensive Unit Testing**: Create `tests/test_k8s_bootstrap.py` covering GPU detection, fallback, and reachability routing.

---

## 2. Key Deliverables

- `src/devops_cli/config/settings.py`: Added `OpenWebUIConfig` and `ValkeyConfig.url` schema fields.
- `src/devops_cli/commands/k8s/cluster_runtime.py`: Syntax cleanup and GPU detection status reporting.
- `src/devops_cli/commands/k8s/bootstrap.py`: Startup message reporting and post-deploy `configure_urls` invocation.
- `src/devops_cli/commands/k8s/networking.py`: Non-blocking socket probe, scheme preservation, and full settings persistence.
- `tests/test_k8s_bootstrap.py`: Comprehensive test suite for GPU detection, fallback, and NodePort reachability.
