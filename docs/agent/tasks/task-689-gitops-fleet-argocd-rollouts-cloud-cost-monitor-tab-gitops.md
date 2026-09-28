# Task 689: GitOps Fleet, ArgoCD Rollouts & Cloud Cost Monitor (`tab-gitops`)

**Issue**: [#689](https://github.com/dan-petty/devops-cli/issues/689)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/github`, `priority/p1-high`

---

## 1. Description & Objectives

Brings continuous deployment and cloud infrastructure FinOps into situational awareness.

#### Key Deliverables:
- Context & Rationale*: Brings continuous deployment and cloud infrastructure FinOps into situational awareness.
- ArgoCD Application Fleet*: Tree view of deployed GitOps applications showing sync status (`Synced`, `OutOfSync`) and health status (`Healthy`, `Progressing`, `Degraded`). One-key app synchronization trigger (`s` -> `devops argo cd apps sync`).
- Argo Rollout Canary Visualizer*: Live step-by-step rollout progression with canary traffic weight and automated metric analysis results.
- IaC Drift & Infracost Spend Tracker*: OpenTofu workspace state overview, drift status badge, and monthly cloud cost forecast summary (`devops tf cost`).
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
