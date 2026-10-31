# Tasks

## 1. Delete `_K8sModule` and Export Public Names
- [ ] 1.1 Remove `_K8sModule`, `_forward_submodule_attr`, `_PATCH_TARGET_MAP`, and private attributes from `src/devops_cli/commands/k8s/__init__.py`; verify `python -c "import devops_cli.commands.k8s as m; assert not [n for n in m.__all__ if n.startswith('_')]"` exits 0
- [ ] 1.2 Regenerate documentation with `uv run devops docs generate --sync-readme`

## 2. Move Stack Catalogs and URL Resolution to `k8s/`
- [ ] 2.1 Move `HELM_REPOS_BY_STACK`, `HELM_RELEASES_BY_STACK`, `MANIFESTS_BY_STACK`, `KUSTOMIZATIONS_BY_STACK`, and URL resolution helpers to `src/devops_cli/k8s/stacks.py`; verify imports and tests pass via `uv run pytest tests/k8s/`
- [ ] 2.2 Move Argo CD host override derivation to `src/devops_cli/k8s/argocd_overrides.py`; verify with `uv run pytest tests/k8s/test_k8s_argocd_overrides.py`
- [ ] 2.3 Unify context resolution on `resolve_context` and delete `resolve_effective_context`; verify with `uv run pytest tests/commands/k8s/test_k8s_context.py`

## 3. Route Subprocesses and Clients Through Seams
- [ ] 3.1 Route kubectl, helm, minikube, and port-forward through `run_subprocess` and remove `_run_cmd` and `_kubectl` wrappers; verify with `uv run pytest tests/commands/k8s/`
- [ ] 3.2 Route Kubernetes client loading through `KubernetesService`; verify with `uv run pytest tests/commands/k8s/test_k8s_runtime_cmd.py`

## 4. Test Files Migration to Public Interfaces and Process Fakes
- [ ] 4.1 Migrate `test_k8s_rbac_audit.py`, `test_k8s_runtime_cmd.py`, and `test_k8s_run_job.py` to `process_fake`; verify with `uv run pytest tests/commands/k8s/test_k8s_rbac_audit.py tests/commands/k8s/test_k8s_runtime_cmd.py tests/commands/k8s/test_k8s_run_job.py`
- [ ] 4.2 Migrate `test_k8s_networking.py`, `test_k8s_proxy_addressing.py`, and `test_k8s_tls.py` to `process_fake` and `fake_cluster`; verify with `uv run pytest tests/commands/k8s/test_k8s_networking.py tests/commands/k8s/test_k8s_proxy_addressing.py tests/commands/k8s/test_k8s_tls.py`
- [ ] 4.3 Migrate `test_k8s_bootstrap.py`, `test_k8s_devops_stack.py`, `test_k8s_logging_stack.py`, and `test_k8s_qdrant_security.py` to `process_fake`; verify with `uv run pytest tests/commands/k8s/test_k8s_bootstrap.py tests/commands/k8s/test_k8s_devops_stack.py tests/commands/k8s/test_k8s_logging_stack.py tests/commands/k8s/test_k8s_qdrant_security.py`
- [ ] 4.4 Dissolve `test_k8s.py` into behaviour files (`test_stack_deploy.py`, `test_cluster_bootstrap.py`, `test_stack_teardown.py`, `test_argocd_deploy.py`) and delete `test_subsystem_containment_and_redaction.py`; verify with `uv run pytest tests/commands/k8s/`
- [ ] 4.5 Move manifest invariant tests to `tests/invariants/test_k8s_manifests.py`; verify with `uv run pytest tests/invariants/test_k8s_manifests.py`

## 5. Verification and Quality Gate
- [ ] 5.1 Verify zero internal patches and zero private imports in `tests/commands/k8s/`
- [ ] 5.2 Verify test names conform to ASD-STE100 and do not end in `_success`, `_failure`, `_basic`, or `_command`
- [ ] 5.3 Run `uv run devops openspec check` and `uv run devops ci`

## Workflow follow-up
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
