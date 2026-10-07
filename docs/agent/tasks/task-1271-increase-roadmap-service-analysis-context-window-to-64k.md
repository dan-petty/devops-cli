# Task: Increase Roadmap Service Analysis Context Window to 64k (#1271)

**Issue**: [#1271](https://github.com/dan-petty/devops-cli/issues/1271)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: scope/k8s

## Description
Increases the `ai.tasks.analysis.context_window` setting for the in-cluster `roadmap-service` (and batch jobs in namespace `devops`) from 16k (`16384`) to 64k (`65536`) tokens in `k8s/devops/configmap.example.yaml` (`devops-cli-config`).

This expanded context window provides sufficient budget for `devops roadmap refine` to collect documentation, architecture decision records (`docs/adr/*.md`), cited code, identifier matches, and repository directory structures during automated candidate refinement without prematurely truncating essential architectural context.

## Acceptance Criteria
- [x] `k8s/devops/configmap.example.yaml` specifies `ai.tasks.analysis.context_window: 65536`.
- [x] `SAMPLE_TEMPLATE` in `tests/test_k8s_configmap.py` reflects `context_window: 65536` under `analysis`.
- [x] `tests/test_k8s_devops_runtime.py` asserts that `settings.ai.tasks.analysis.context_window == 65536`.
- [x] `tests/test_k8s_roadmap_service.py` asserts that `settings.ai.tasks.analysis.context_window == 65536`.
- [x] All test suites pass with 100% green status.
- [x] `changelog.d/1271.md` changelog fragment is created.
- [x] `devops pr check-readiness` passes for the PR.
- Pending a person: live rollout verification:
  - `kubectl apply -f k8s/devops/configmap.yaml && kubectl -n devops rollout restart deploy/roadmap-service`
  - `kubectl -n devops rollout status deploy/roadmap-service --timeout=120s` succeeds.
  - `kubectl -n devops exec deploy/roadmap-service -- cat /config/devops-cli.yaml` shows `context_window: 65536`.

## Deliverables
- [x] `k8s/devops/configmap.example.yaml`
- [x] `tests/test_k8s_configmap.py`
- [x] `tests/test_k8s_devops_runtime.py`
- [x] `tests/test_k8s_roadmap_service.py`
- [x] `docs/agent/tasks/task-1271-increase-roadmap-service-analysis-context-window-to-64k.md`
- [x] `changelog.d/1271.md`
