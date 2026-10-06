# Task 1261: Argo CD Git-Source TargetRevision Tracks Main While Service Image Pin Tracks Release

**Issue**: [#1261](https://github.com/dan-petty/devops-cli/issues/1261)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: type/bug, scope/k8s

---

## 1. Description & Objectives

Previously, Argo CD git-source `targetRevision` fields across `k8s/argocd/` were coupled to active release branches (`release/vX.Y.Z`). This required keeping release branches in lockstep with `main` via manual intermediate merge commits for Argo CD to pick up configuration updates and Kustomize overlays.

This deliverable decouples manifest tracking from container release images:
- **Git Source Revision Alignment**: All git-source `targetRevision` fields under `k8s/argocd/` (the root `cluster.yaml` and all 20 leaf Applications) track `main`.
- **Release Version Pinning for Container Images**: Container workloads in `k8s/devops/kustomization.yaml` continue to pin authoritative release tags (`vX.Y.Z`), validated by `devops release check` against `pyproject.toml`.
- **Validation & Prepare Simplification**: `_verify_argocd_target_revisions` verifies uniform `main` revisions under `k8s/argocd/`, and `_apply_argocd_target_revisions` ensures git sources stay on `main`.

---

## 2. Acceptance Criteria

- [x] All git-source `targetRevision` fields across `k8s/argocd/` set to `main`.
- [x] `src/devops_cli/commands/release.py` updated to verify and apply `main` across Argo CD git sources while maintaining the release image tag check in `k8s/devops/kustomization.yaml`.
- [x] `tests/test_k8s_argocd_apps.py` validates all 21 Application manifests point to `targetRevision: main`.
- [x] `tests/test_release.py` validates `release prepare` and `release check` behavior under `main` targetRevisions.
- [x] `k8s/README.md` updated to document `cluster.yaml` tracking `main`.
- [x] Changelog fragment `changelog.d/1261.md` authored.
- [x] All 14 CI quality gates pass in `uv run devops ci`.

---

## 3. Deliverables

- [x] `k8s/argocd/bootstrap/cluster.yaml`: Updated `targetRevision` to `main`.
- [x] `k8s/argocd/apps/*.yaml`: Updated all 20 leaf applications to `targetRevision: main`.
- [x] `src/devops_cli/commands/release.py`: Updated revision resolution and verification logic.
- [x] `tests/test_k8s_argocd_apps.py`: Updated test assertions for `main`.
- [x] `tests/test_release.py`: Updated release check and prepare test cases.
- [x] `k8s/README.md`: Updated GitOps architecture description.
- [x] `changelog.d/1261.md`: Changelog fragment.
- [x] `docs/agent/tasks/task-1261-argocd-target-revision-main.md`: Task documentation.
