# Agent Task Tracking Index

> **Modular Task Architecture**: To eliminate git merge conflicts between concurrent feature branches, task tracking has migrated from this monolithic file to modular, per-task documents under [`docs/agent/tasks/`](tasks/README.md).
>
> **Rule**: Each feature, bug fix, or refactor branch must ONLY create or modify its own dedicated task file: `docs/agent/tasks/task-<issue>-<slug>.md`. Updates must only be committed in the context of the functional changes delivering that task.

---

## Active Milestone: v0.2.15

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

---

## Historical Archives

Historical tasks and development phases from prior releases and migrations are archived in:
- [`docs/agent/archive/historical-phases-1-to-50.md`](archive/historical-phases-1-to-50.md) (Phases 1 through 51.5)
