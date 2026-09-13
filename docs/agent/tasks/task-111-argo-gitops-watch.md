# Task 111: Automated GitOps Drift Detection & Webhook Synchronization

**Issue**: [#111](https://github.com/dan-petty/devops-cli/issues/111)
**PR**: [#195](https://github.com/dan-petty/devops-cli/pull/195)
**Status**: In Review
**Milestone**: `v0.2.17`
**Priority**: `priority/p1-high`
**Scope**: `scope/k8s`

---

## 1. Description & Architectural Objectives

Implement an automated GitOps drift detection and synchronization watch engine (`devops argo gitops watch`) that:
1. Monitors local Kubernetes and Helm manifest directories (`k8s/`, Helm charts, values files) for file modifications.
2. Applies debounced change aggregation to eliminate redundant triggers during rapid edits.
3. Automatically triggers ArgoCD application sync (or webhook notification) against the target ArgoCD application or local dev cluster.
4. Provides live terminal output and progress reporting with Rich formatting.
5. Adheres to zero-boilerplate and architectural invariants ($\le 10$ cyclomatic complexity, $\le 5$ nesting depth) with $\ge 90\%$ test coverage.

---

## 2. Planned Changes

1. **`src/devops_cli/argo/gitops.py`**:
   - Manifest change detector tracking modification timestamps and file hashes.
   - Debounce logic with configurable delay.
   - ArgoCD sync/webhook dispatcher.
   - Live status rendering table/panel.
2. **`src/devops_cli/commands/argo.py`**:
   - Register `gitops_app` group under `devops argo` and `devops argo cd`.
   - Subcommand `devops argo gitops watch` with options:
     - `--path` / `-p`: Manifest paths or directories (default: `k8s`).
     - `--app-name` / `-a`: Target ArgoCD application name.
     - `--debounce-ms`: Debounce delay in milliseconds (default: 500).
     - `--interval`: Watch polling/check interval in seconds (default: 1.0).
     - `--max-events`: Maximum change events to process before exiting (useful for testing/CI).
     - `--once`: Process current drift once and exit immediately.
     - `--dry-run`: Preview changes without triggering sync API.
3. **`tests/test_argo_gitops.py`**:
   - Comprehensive unit and integration test suite targeting $\ge 90\%$ coverage.

---

## 3. Progress Tracking

- [x] Ground issue in GitHub tracking (#111) with `status/in-progress`.
- [x] Author task tracking file `docs/agent/tasks/task-111-argo-gitops-watch.md`.
- [x] Checkout dedicated topic branch `feat/111-argo-gitops-watch`.
- [x] Author `src/devops_cli/argo/gitops.py`.
- [x] Add `gitops watch` command in `src/devops_cli/commands/argo.py`.
- [x] Author comprehensive tests in `tests/test_argo_gitops.py`.
- [x] Verify test suite and quality gates pass cleanly.
- [ ] Commit with concise Conventional Commit message.
- [ ] Open Draft Pull Request targeting `release/v0.2.17`.
- [ ] Transition PR to ready, verify merge readiness, squash-merge into `release/v0.2.17`, and close issue #111.
