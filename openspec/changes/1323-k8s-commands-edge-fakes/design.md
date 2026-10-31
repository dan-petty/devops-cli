# Design

## Context

See proposal.md for motivation and scope (#1323).
Tests covering `commands/k8s/` historically monkeypatched internal module functions (`_run_cmd`, `_cluster_reachable`, `_minikube_running`) and `run_subprocess` on `devops_cli` submodules. Product code in `src/devops_cli/commands/k8s/__init__.py` replaced its module `__class__` with `_K8sModule` to intercept attribute assignments and forward them to internal submodules.

## Goals / Non-Goals

**Goals:**
- Delete `_K8sModule` and forwarder tables from `commands/k8s/__init__.py`.
- Ensure all subprocess calls in `commands/k8s/` invoke `run_subprocess`.
- Move stack catalog data and URL helpers to `devops_cli.k8s` under public names.
- Replace all monkeypatches of `devops_cli` symbols in `tests/commands/k8s/` with calls to `process_fake` and `fake_cluster`.
- Split `tests/commands/k8s/test_k8s.py` into focused behaviour test files.
- Move manifest validation tests to `tests/invariants/test_k8s_manifests.py`.

**Non-Goals:**
- Modify the command-line flags or external behaviour of `devops k8s` commands.
- Rewrite cluster deployment logic or manifest content.

## Decisions

### 1. Remove `_K8sModule` and Clean Up `__all__`
- **Decision**: Delete `_K8sModule`, `_forward_submodule_attr`, `_PATCH_TARGET_MAP`, and the name sets in `commands/k8s/__init__.py`. Export only public command functions and Typer apps in `__all__`.
- **Alternative considered**: Keep `_K8sModule` as a shim for existing tests.
  - *Rejected*: AGENTS.md rule prohibits backward-compatibility shims before 1.0.0. The purpose of #1323 is to eliminate mock-detection branches and patch routing.

### 2. Move Domain Stack Catalogs and URL Resolution to `k8s/`
- **Decision**: Move `_HELM_REPOS_BY_STACK`, `_HELM_RELEASES_BY_STACK`, `_MANIFESTS_BY_STACK`, and URL resolution helpers (`_parse_minikube_service_url`, `_extract_first_node_ip`, `_resolve_k8s_node_port_url`, `_resolve_accessible_url`) to `src/devops_cli/k8s/` under public names (`HELM_REPOS_BY_STACK`, `HELM_RELEASES_BY_STACK`, etc.). Move Argo CD host override derivation to `src/devops_cli/k8s/argocd_overrides.py`.
- **Alternative considered**: Keep catalog dictionaries in `stack_lifecycle.py`.
  - *Rejected*: Invariant tests and command modules must share a single public domain source of truth.

### 3. Route Subprocesses Through `run_subprocess` Seam
- **Decision**: Replace `_run_cmd` and `_kubectl` in `commands/k8s/` with calls to `run_subprocess`. Delete the local wrappers.
- **Alternative considered**: Patch `subprocess.run` inside test fixtures.
  - *Rejected*: Issue #775 and #1307 establish `run_subprocess` with `ProcessFake` as the single process seam.

### 4. Dissolve `test_k8s.py` and Move Invariant Tests
- **Decision**: Split `test_k8s.py` into behaviour-oriented test files (`test_stack_deploy.py`, `test_cluster_bootstrap.py`, `test_stack_teardown.py`, etc.). Move tests that read files under `k8s/` to `tests/invariants/test_k8s_manifests.py`.
- **Alternative considered**: Keep the monolithic `test_k8s.py`.
  - *Rejected*: Monolithic test files hide behaviour and mix command testing with filesystem invariant assertions.

## Risks / Trade-offs

- [Coverage drop during test file split] → Run coverage check after each split to verify no test paths are lost.
- [Hidden dependencies on `_K8sModule` forwarding] → Grep the entire repository for references to `devops_cli.commands.k8s._` before deleting.
