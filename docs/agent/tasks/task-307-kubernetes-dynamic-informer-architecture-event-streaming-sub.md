# Task 307: Kubernetes Dynamic Informer Architecture, Event Streaming & Subprocess Elimination Research

**Issue**: [#307](https://github.com/dan-petty/devops-cli/issues/307)
**Status**: Done
**Milestone**: `v0.2.22`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/k8s`, `priority/p0-critical`

---

## 1. Description & Objectives

Eliminate external `kubectl` binary process spawning overhead and rigid error handling across Kubernetes subcommands by introducing direct in-process Python `kubernetes` client integration, an in-memory `KubernetesService` layer with TTL response caching, and a real-time `ResourceInformer` streaming event watcher.

### Key Deliverables Completed:
- [x] **KubernetesService Singleton Architecture (`src/devops_cli/k8s/service.py`)**:
  - Direct in-process integration with `kubernetes.client.CoreV1Api`, `AppsV1Api`, and `VersionApi`.
  - In-memory reachability probing (`is_cluster_reachable`), node listing (`list_nodes`), pod listing (`list_pods`), and service endpoint resolution (`resolve_service_endpoint`) with bounded TTL response caching (`DEFAULT_K8S_CACHE_TTL_SECONDS`).
  - Native atomic kubeconfig context switching (`switch_context`) without `kubectl config use-context` process churn.
  - Native pod log streaming (`read_pod_logs`) directly from `CoreV1Api` with stream generators.
- [x] **ResourceInformer Architecture (`src/devops_cli/k8s/informer.py`)**:
  - Event streaming watcher wrapping `kubernetes.watch.Watch` to stream real-time cluster events (`ADDED`, `MODIFIED`, `DELETED`, `ERROR`) into thread-safe in-memory collections without busy-polling.
  - Real-time `stream_events()` generator and background worker loop.
  - Typed `K8sEvent` and `K8sInformerState` Pydantic models in `src/devops_cli/models/k8s.py`.
- [x] **Subprocess Elimination & Command Refactoring**:
  - Refactored `cluster_runtime._cluster_reachable` to probe in-process first.
  - Refactored `cluster_context.switch_context`, `status`, and `_execute_legacy_kubectl_logs` to integrate `KubernetesService`.
  - Refactored `diagnostics._build_pods_table` and `pods_cmd` `--watch` to stream live events via `ResourceInformer`.
  - Refactored `networking._detect_service_url` to resolve endpoints in-process natively.
- [x] **Automated Tests & Quality Gates**:
  - 14 comprehensive unit tests in `tests/test_k8s_service.py` with structural tuple equality checks.
  - 267 passing Kubernetes test assertions with 91% coverage across `src/devops_cli/k8s/`.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ enforced project-wide.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
