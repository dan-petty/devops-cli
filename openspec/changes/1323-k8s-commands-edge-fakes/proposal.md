# Proposal

## Why

Issue #1323 delivers Phase E package test refactoring for Kubernetes commands (`commands/k8s/`) under parent issue #1307. The tests under `tests/commands/k8s/` frequently patch internal `devops_cli` symbols (`_run_cmd`, `_cluster_reachable`, `_minikube_running`, `run_subprocess`), import private `_`-prefixed names, and construct hand-rolled mocks. Product code in `commands/k8s/__init__.py` implements a patch-forwarding proxy class (`_K8sModule`) to route monkeypatches to underlying submodules. This change moves command adapters to external process and cluster fakes, deletes `_K8sModule`, moves domain catalog tables to `k8s/`, and ensures tests assert against public interfaces.

## What Changes

- Delete `_K8sModule`, `_forward_submodule_attr`, `_PATCH_TARGET_MAP`, and the attribute sets from `commands/k8s/__init__.py`.
- Remove all private `_`-prefixed exports from `commands/k8s/__init__.__all__`.
- Route `kubectl`, `helm`, `minikube`, and `port-forward` through the process runner seam (`run_subprocess`); remove local `_run_cmd` and `_kubectl` wrappers.
- Route Kubernetes client loading in `commands/k8s/` through `KubernetesService`.
- Move stack catalogs (`_HELM_REPOS_BY_STACK`, `_HELM_RELEASES_BY_STACK`, `_MANIFESTS_BY_STACK`, `_KUSTOMIZATIONS_BY_STACK`) and URL resolution to public modules under `devops_cli.k8s`.
- Move Argo CD host override derivation to `devops_cli.k8s.argocd_overrides`.
- Delete `resolve_effective_context`; unify context resolution on `resolve_context`.
- Delete internal patches and private imports across `tests/commands/k8s/`.
- Dissolve monolithic `test_k8s.py` into distinct behaviour test files.
- Move manifest invariant tests into `tests/invariants/test_k8s_manifests.py`.
- This change alters no consumer-observed CLI behaviour or command syntax, so it sets `skip_specs: true`.
- This change fits one pull request.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `src/devops_cli/commands/k8s/__init__.py`: removes `_K8sModule` class and exports public symbols only.
- `src/devops_cli/commands/k8s/`: routes subprocess and client calls through seams; removes internal helpers.
- `src/devops_cli/k8s/`: hosts public stack catalog and URL resolution helpers.
- `tests/commands/k8s/`: migrates all tests to `process_fake`, `fake_cluster`, and public interfaces.
- `tests/invariants/`: receives manifest invariant assertions from `tests/commands/k8s/`.

## Feasibility

- The `process_fake` fixture in `tests/support/fakes/process.py` provides deterministic responses for child processes (`kubectl`, `helm`, `minikube`).
- The `fake_cluster` fixture in `tests/support/fakes/kubernetes.py` provides API resource emulation for `KubernetesService`.
- `k8s/argocd_overrides.py` already handles Argo CD Kustomize host overrides and accepts public parameters.
- `run_subprocess` is established across `commands/` and `github/` as the standard subprocess seam.

## Existing Tool Considered

- `ProcessFake` provides hermetic process execution without shell dependencies.
- `FakeCluster` provides in-memory Kubernetes API simulation.
- Reusing the existing shared fakes eliminates 265 internal patch sites and 76 private imports, deleting `_K8sModule` and custom test mock classes without adding external dependencies.
