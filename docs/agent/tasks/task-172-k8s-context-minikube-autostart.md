# Task 172: Configurable K8s Context Setting & Conditional Minikube Autostart

**Issue**: [#172](https://github.com/dan-petty/devops-cli/issues/172)
**PR**: [#174](https://github.com/dan-petty/devops-cli/pull/174)
**Status**: In Review
**Milestone**: `v0.2.17`
**Priority**: `priority/p1-high`
**Scope**: `scope/k8s`

---

## 1. Description & Architectural Objectives

Implement configurable Kubernetes cluster context setting (`k8s.context`) across devops-cli configuration and CLI commands. Enable conditional Minikube autostart behavior such that Minikube only autostarts when configured as the active cluster context (or explicitly requested via environment variable `DEVOPS_MINIKUBE_AUTOSTART=true` / `DEVOPS_K8S_AUTOSTART_MINIKUBE=true`), and automatically start Minikube if it is stopped when switching context to `minikube`.

### Key Objectives
1. **Configurable K8s Context Setting (`k8s.context`)**:
   - Add `k8s.context` setting to `KubernetesConfig` in `src/devops_cli/config/settings.py`.
   - Add `K8S_CONTEXT = "k8s.context"` in `src/devops_cli/config/options.py`.
   - Add `ENV_K8S_CONTEXT = "DEVOPS_CLI_K8S_CONTEXT"` and registration in `src/devops_cli/config/env.py`.
   - Support `devops config get/set/show` for `k8s.context`.
   - Update `config.example.yaml` and active `config.yaml`.
2. **Conditional Minikube Autostart Subsystem (`src/devops_cli/commands/k8s/cluster_runtime.py`)**:
   - Centralize Minikube start sequence in `_start_minikube(dry_run: bool = False)` with GPU detection and CPU fallback.
   - Implement `should_autostart_minikube(target_context: str | None = None) -> bool`:
     - Default to configured context (`settings.k8s.context`).
     - Respect explicit environment variable overrides (`DEVOPS_MINIKUBE_AUTOSTART`, `DEVOPS_K8S_AUTOSTART_MINIKUBE`).
     - If context is `minikube`: autostart (unless explicitly disabled).
     - If context is a different cluster: do not autostart (unless explicitly enabled).
   - Update `devops devcontainer post-start` and `bootstrap-k8s` in `src/devops_cli/commands/devcontainer.py` to use `should_autostart_minikube()`.
   - Clean hardcoded `"DEVOPS_MINIKUBE_AUTOSTART": "true"` from `.devcontainer/devcontainer.json` and `templates/devcontainer.json.j2`.
3. **Context-Switching Autostart (`src/devops_cli/commands/k8s/cluster_context.py`)**:
   - When switching context to `minikube` via `devops k8s switch-context minikube`:
     - Check if Minikube is running; if stopped, automatically launch it.
     - Update active configuration `settings.k8s.context = "minikube"` and save.
   - When switching context to another cluster:
     - Do not launch Minikube.
     - Update active configuration `settings.k8s.context = <name>` and save.
4. **Context Defaulting for K8s Commands**:
   - Default `--context` option across K8s commands (`deploy-stack`, `status`, `teardown-stack`, `_cluster_reachable`) to `settings.k8s.context`.
5. **Comprehensive Test-First Coverage**:
   - Add unit and integration tests covering context loading, environment variable overrides, conditional autostart predicates, context switching, and devcontainer lifecycle hooks.

---

## 2. Implementation Checklist

- [x] Author task tracking file `docs/agent/tasks/task-172-k8s-context-minikube-autostart.md`
- [x] Update `docs/agent/task.md` index
- [x] Author comprehensive tests in `tests/test_k8s_cmd.py`, `tests/test_config.py`, and `tests/test_devcontainer.py`
- [x] Implement `KubernetesConfig` in `src/devops_cli/config/settings.py`
- [x] Implement `K8S_CONTEXT` in `options.py`, `env.py`, and `commands/config.py`
- [x] Implement `_start_minikube` and `should_autostart_minikube` in `src/devops_cli/commands/k8s/cluster_runtime.py`
- [x] Update `devops k8s switch-context` in `src/devops_cli/commands/k8s/cluster_context.py`
- [x] Update `commands/k8s/bootstrap.py` and `commands/k8s/stack_lifecycle.py` to use cluster runtime helpers
- [x] Update `commands/devcontainer.py` to use `should_autostart_minikube()`
- [x] Update `config.example.yaml` and `config.yaml`
- [x] Update `.devcontainer/devcontainer.json` and `templates/devcontainer.json.j2`
- [x] Run `devops docs generate --sync-readme`
- [x] Document DevContainer Minikube lifecycle and conditional autostart in `docs/DEVCONTAINER_USAGE.md`
- [x] Document external cluster connectivity (Docker Desktop, kind/k3s, cloud EKS/GKE/AKS) in `docs/DEVCONTAINER_USAGE.md`
- [x] Update Knowledge Base domain topics and tools (`cloud_native_kubernetes_and_gitops.md`, `minikube.md`, `kubectl.md`, `k8s_stack_deployment.md`, `devcontainer_lifecycle.md`)
- [x] Synchronize `docs/CONFIGURATION.md` with field descriptions for `k8s.context`
- [x] Validate entire CI suite via `uv run devops ci`
