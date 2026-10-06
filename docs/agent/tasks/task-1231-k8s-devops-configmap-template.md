# Task: Dynamically Generate DevOps ConfigMap from Active Config and Gitignore (#1231)

**Issue**: [#1231](https://github.com/dan-petty/devops-cli/issues/1231)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p2-medium
**Scope**: scope/k8s

## Description
The committed Kubernetes manifest `k8s/devops/configmap.yaml` previously contained concrete repository references and user account names in the git-tracked version. When users added repositories or adjusted their bot machine account, modifications would introduce local uncommitted diffs or risk leaking environment identifiers.

This deliverable:
1. **Sanitizes ConfigMap Template**: Establishes `k8s/devops/configmap.example.yaml` as the committed template using standard placeholder repositories (`owner/repo`) and machine account (`devops-bot`).
2. **Gitignores Runtime Manifest**: Untracks `k8s/devops/configmap.yaml` from version control and adds it to `.gitignore`, preventing user repository configurations or active bot accounts from ever being committed.
3. **Dynamic Generation & Synchronization**: Introduces `devops_cli.k8s.configmap` (`ensure_devops_configmap`, `render_devops_configmap_content`) to dynamically generate `k8s/devops/configmap.yaml` from active settings (`service.repos`, `service.machine_account`, or `k8s.github_account`) when running `devops k8s deploy-stack`, while preserving existing repos and settings if active configuration is unset.
4. **Resilient Kustomize & Render Integration**: Updates `_apply_single_manifest` in `stack_lifecycle.py` and `_render_kustomize_dir` in `template.py` to automatically materialize `k8s/devops/configmap.yaml` if missing before executing `kubectl apply` or `kubectl kustomize`.
5. **Comprehensive Tests**: Adds unit and integration tests in `tests/test_k8s_configmap.py` and updates `tests/test_k8s_devops_runtime.py`, `tests/test_k8s_devops_stack.py`, and `tests/test_k8s_roadmap_service.py` to seamlessly validate against the example template or generated configmap.

## Acceptance Criteria
- [x] `k8s/devops/configmap.example.yaml` is committed with sanitized placeholders.
- [x] `/k8s/devops/configmap.yaml` is ignored in `.gitignore` and untracked from git.
- [x] `ensure_devops_configmap` dynamically generates and synchronizes `configmap.yaml` from active configuration.
- [x] `devops k8s deploy-stack --stack devops` synchronizes `configmap.yaml` before applying manifests.
- [x] All 14 CI quality gates pass via `uv run devops ci`.

## Deliverables
- [x] `src/devops_cli/k8s/configmap.py`
- [x] `src/devops_cli/k8s/__init__.py`
- [x] `src/devops_cli/k8s/template.py`
- [x] `src/devops_cli/commands/k8s/stack_lifecycle.py`
- [x] `.gitignore`
- [x] `k8s/devops/configmap.example.yaml`
- [x] `k8s/README.md`
- [x] `tests/test_k8s_configmap.py`
- [x] `tests/test_k8s_devops_runtime.py`
- [x] `tests/test_k8s_devops_stack.py`
- [x] `tests/test_k8s_roadmap_service.py`
- [x] `changelog.d/1231.md`
- [x] Task file `docs/agent/tasks/task-1231-k8s-devops-configmap-template.md`.
