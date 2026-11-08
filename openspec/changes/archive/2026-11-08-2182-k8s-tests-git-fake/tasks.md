# Tasks

## 1. Test File Migrations

- [x] 1.1 Migrate `tests/commands/k8s/test_k8s.py`: remove `_git` and `_commit`, update `_Cluster` and `applications_repo`
  - Verification: `! git grep -n -w -e _git -e _commit tests/commands/k8s/test_k8s.py`
  - Verification: `uv run pytest tests/commands/k8s/test_k8s.py -n 0`
- [x] 1.2 Migrate `tests/k8s/test_k8s_argocd_gate.py`: remove `_git_run`, use `git_fake` with in-memory tarball and fake kubectl
  - Verification: `! git grep -n -w _git_run tests/k8s/test_k8s_argocd_gate.py`
  - Verification: `uv run pytest tests/k8s/test_k8s_argocd_gate.py -n 0`
- [x] 1.3 Migrate `tests/k8s/test_k8s_argocd_overrides.py`: remove `_repo`, use `git_fake` and guarded execution recording
  - Verification: `! git grep -n -w _repo tests/k8s/test_k8s_argocd_overrides.py`
  - Verification: `uv run pytest tests/k8s/test_k8s_argocd_overrides.py -n 0`
- [x] 1.4 Migrate `tests/invariants/test_k8s_argocd_apps.py`: remove `test_this_repository_passes_the_argocd_gate`, evaluate regex in python for finalizers
  - Verification: `uv run pytest tests/invariants/test_k8s_argocd_apps.py -n 0`
- [x] 1.5 Migrate `tests/config/test_k8s_devops_runtime.py`: remove `subprocess.run` calling `git ls-files`
  - Verification: `! git grep -n subprocess tests/config/test_k8s_devops_runtime.py`
  - Verification: `uv run pytest tests/config/test_k8s_devops_runtime.py -n 0`

## 2. Invariants and Verification

- [x] 2.1 Verify no helper remnants remain across the five files
  - Verification: `! git grep -n -w -e _git_run tests/k8s/test_k8s_argocd_gate.py`
  - Verification: `! git grep -n -w -e _git -e _commit tests/commands/k8s/test_k8s.py`
  - Verification: `! git grep -n -w -e _repo tests/k8s/test_k8s_argocd_overrides.py`
- [x] 2.2 Measure before and after execution times
  - Verification: `uv run pytest tests/commands/k8s/test_k8s.py tests/k8s/test_k8s_argocd_gate.py tests/k8s/test_k8s_argocd_overrides.py tests/invariants/test_k8s_argocd_apps.py tests/config/test_k8s_devops_runtime.py -n 0 --durations=0`
- [x] 2.3 Validate OpenSpec change
  - Verification: `uv run devops openspec check`
- [x] 2.4 Full CI validation
  - Verification: `uv run devops ci`
