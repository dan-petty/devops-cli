# Agent Task Tracking Index

> **Modular Task Architecture**: To eliminate git merge conflicts between concurrent feature branches, task tracking has migrated from this monolithic file to modular, per-task documents under [`docs/agent/tasks/`](tasks/README.md).
>
> **Rule**: Each feature, bug fix, or refactor branch must ONLY create or modify its own dedicated task file: `docs/agent/tasks/task-<issue>-<slug>.md`. Updates must only be committed in the context of the functional changes delivering that task.

---

## Active Milestone: v0.2.16

| Issue | PR | Title | Status | Task File |
| :--- | :--- | :--- | :--- | :--- |
| [#131](https://github.com/dan-petty/devops-cli/issues/131) | [#134](https://github.com/dan-petty/devops-cli/pull/134) | Deploy Squid Caching Proxy with SSL-Bump, Observability & Failover Handling | `Done` | [`task-131-k8s-squid-cache-ollama.md`](tasks/task-131-k8s-squid-cache-ollama.md) |
| [#132](https://github.com/dan-petty/devops-cli/issues/132) | [#133](https://github.com/dan-petty/devops-cli/pull/133) | Modernize AI Chat CLI with Rich Rendering & Persona Orange Integration | `Done` | [`task-132-ai-chat-persona-orange.md`](tasks/task-132-ai-chat-persona-orange.md) |
| [#135](https://github.com/dan-petty/devops-cli/issues/135) | [#136](https://github.com/dan-petty/devops-cli/pull/136) / [#143](https://github.com/dan-petty/devops-cli/pull/143) | Review Pod Restarts, Eliminate Cgroup OOM Kills & Optimize Resource Limits | `Done` | [`task-135-k8s-pod-restarts-resource-limits.md`](tasks/task-135-k8s-pod-restarts-resource-limits.md) |
| [#137](https://github.com/dan-petty/devops-cli/issues/137) | [#138](https://github.com/dan-petty/devops-cli/pull/138) | Context Document Compaction Engine (`devops docs compact`) | `Done` | [`task-137-docs-compaction-engine.md`](tasks/task-137-docs-compaction-engine.md) |
| [#139](https://github.com/dan-petty/devops-cli/issues/139) | [#140](https://github.com/dan-petty/devops-cli/pull/140) | Refine AI Chat Streaming Markdown Formatting & Thinking Display | `Done` | [`task-139-ai-chat-markdown-formatting.md`](tasks/task-139-ai-chat-markdown-formatting.md) |
| [#141](https://github.com/dan-petty/devops-cli/issues/141) | [#143](https://github.com/dan-petty/devops-cli/pull/143) | Resolve Squid Proxy Root CA, Build Image, and Enable Proxy Across Cluster | `Done` | [`task-141-squid-proxy-cluster-enablement.md`](tasks/task-141-squid-proxy-cluster-enablement.md) |
| [#142](https://github.com/dan-petty/devops-cli/issues/142) | TBD | High-Throughput LLM Gateway & Distributed Model Router | `Ready` | [`task-142-llm-gateway-distributed-router.md`](tasks/task-142-llm-gateway-distributed-router.md) |

---

## Milestone: v0.2.15

| Issue | PR | Title | Status | Task File |
| :--- | :--- | :--- | :--- | :--- |
| [#88](https://github.com/dan-petty/devops-cli/issues/88) | [#93](https://github.com/dan-petty/devops-cli/pull/93) | Complete Security Scanner Migration to `BaseSecurityScanner` & `ScannerRegistry` | `Done` | [`task-088-security-scanner-migration.md`](tasks/task-088-security-scanner-migration.md) |
| [#89](https://github.com/dan-petty/devops-cli/issues/89) | [#96](https://github.com/dan-petty/devops-cli/pull/96) | Centralized Kubernetes Logging Stack & LogQL Integration | `Done` | [`task-089-k8s-centralized-logging.md`](tasks/task-089-k8s-centralized-logging.md) |
| [#90](https://github.com/dan-petty/devops-cli/issues/90) | [#97](https://github.com/dan-petty/devops-cli/pull/97) | Infracost FinOps Cloud Cost Engine (`devops tf cost`) | `Done` | [`task-090-infracost-finops-cloud-cost.md`](tasks/task-090-infracost-finops-cloud-cost.md) |
| [#91](https://github.com/dan-petty/devops-cli/issues/91) | [#98](https://github.com/dan-petty/devops-cli/pull/98) | Multi-Cluster ArgoCD Fleet Sync & Rollouts (`devops argo sync --fleet`) | `Done` | [`task-091-argo-fleet-sync.md`](tasks/task-091-argo-fleet-sync.md) |
| [#94](https://github.com/dan-petty/devops-cli/issues/94) | [#95](https://github.com/dan-petty/devops-cli/pull/95) | Eliminate Obsolete Shims, Aliases, Proxy Wrappers & Compatibility Remnants | `Done` | [`task-094-eliminate-obsolete-shims.md`](tasks/task-094-eliminate-obsolete-shims.md) |
| [#99](https://github.com/dan-petty/devops-cli/issues/99) | [#100](https://github.com/dan-petty/devops-cli/pull/100) | Optimize Caching Configuration Across All GitHub Workflows | `Done` | [`task-099-ci-workflows-cache-optimization.md`](tasks/task-099-ci-workflows-cache-optimization.md) |
| [#101](https://github.com/dan-petty/devops-cli/issues/101) | — | Modularize Agent Task Tracking to Eliminate Merge Conflicts | `Done` | [`task-101-modular-agent-task-tracking.md`](tasks/task-101-modular-agent-task-tracking.md) |
| [#102](https://github.com/dan-petty/devops-cli/issues/102) | — | Strengthen Review Prompts, Feedback Dataset Export & Self-Improvement Loop | `Done` | [`task-102-review-feedback-loop-hardening.md`](tasks/task-102-review-feedback-loop-hardening.md) |
| [#103](https://github.com/dan-petty/devops-cli/issues/103) | — | Generalize `devops ai review` for Arbitrary Target Repositories & Multi-Convention Discovery | `Done` | [`task-103-target-agnostic-review-generalization.md`](tasks/task-103-target-agnostic-review-generalization.md) |
| [#104](https://github.com/dan-petty/devops-cli/issues/104) | — | Telemetry Tracing Optimizations, Jaeger Sizing & Fast Failover | `Done` | [`task-104-telemetry-trace-optimizations.md`](tasks/task-104-telemetry-trace-optimizations.md) |

---

## Historical Archives

Historical tasks and development phases from prior releases and migrations are archived in:
- [`docs/agent/archive/historical-phases-1-to-50.md`](archive/historical-phases-1-to-50.md) (Phases 1 through 51.5)
