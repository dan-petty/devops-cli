# Task 637: Prevent deploy-stack and port-forward from Unconditionally Overwriting Config with Localhost

**Issue**: [#637](https://github.com/dan-petty/devops-cli/issues/637)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/k8s`, `priority/p1-high`

---

## 1. Description & Objectives

Running `devops k8s deploy-stack` previously initiated background port-forwarding daemons for all deployed Kubernetes services and automatically rewrote user configuration (`config.yaml`) with `http://localhost:...` endpoints. This clobbered existing remote inference hostnames, multi-node Ollama endpoints (`ai.ollama_urls`), and cluster-accessible services (such as NodePort, LoadBalancer, and Ingress URLs) without caller confirmation or opt-in.

Root causes identified:
1. `stack_lifecycle.py`: Step 6 of `deploy_stack` unconditionally invoked `net.port_forward(...)` without any CLI flag or user opt-in.
2. `networking.py`: `port_forward` unconditionally started background `kubectl port-forward` processes and called `configure_urls(...)` to mutate configuration.
3. `_resolve_accessible_url`: Checked preferred localhost ports *before* testing `detected_url`. Because port-forwarding daemons had just bound localhost ports, localhost probes always succeeded, silently discarding cluster-detected endpoints.
4. `_configure_llm_stack_urls`: Unconditionally assigned `settings.ai.ollama_urls = [ollama_url]`, replacing any configured remote or multi-cluster inference endpoints with a single localhost entry.

### Key Deliverables Completed:
- [x] **Stack Lifecycle Non-Intrusive Defaults** (`src/devops_cli/commands/k8s/stack_lifecycle.py`):
  - Added `--port-forward / --no-port-forward` flag (defaulting to `False`) to `deploy_stack`.
  - Added `--configure-urls / --no-configure-urls` flag (defaulting to `False`) to `deploy_stack`.
  - Only execute `net.port_forward` when `--port-forward` is explicitly requested.
- [x] **Safe Networking & URL Configuration** (`src/devops_cli/commands/k8s/networking.py`):
  - Added `--update-config / --no-update-config` flag (defaulting to `False`) to `port_forward` so port forwarding does not mutate `config.yaml` by default.
  - Inverted priority in `_resolve_accessible_url`: test `detected_url` reachability first; only fall back to localhost ports if `detected_url` is unreachable or unconfigured.
  - In `_configure_llm_stack_urls`: preserve existing `settings.ai.ollama_urls` rather than wiping out remote inference configurations with a single localhost entry.
- [x] **Comprehensive Test Coverage & Architectural Invariant Gates** (`tests/test_k8s.py`, `tests/test_k8s_jaeger.py`, `tests/test_k8s_networking.py`):
  - Added unit test verifying `deploy_stack` defaults do not invoke port-forwarding or configuration rewriting unless requested.
  - Added unit test verifying `port_forward` defaults do not rewrite `config.yaml`.
  - Added unit tests for `_resolve_accessible_url` prioritizing reachable cluster endpoints over localhost fallbacks.
  - 100% compliance across Gated CI validation suite (`uv run devops ci`).
