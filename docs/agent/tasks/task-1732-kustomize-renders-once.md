# Task: Committed Kustomizations Render Once per Test Process, with kubectl's Offline Renderers Run as Real Tools (#1732)

**Issue**: [#1732](https://github.com/dan-petty/devops-cli/issues/1732)
**Scope**: scope/ci
**Feasibility**: A recorder under `subprocess.Popen._execute_child` and `os.posix_spawn`, run over the 158 test files that mention kubectl, found exactly 33 tests that start `kubectl`. None reaches a cluster: the root conftest's session-wide `isolate_kubeconfig` (`tests/conftest.py`) gives every test an empty kubeconfig. Against that kubeconfig, `kubectl config get-contexts -o name` exits 0 with no output. The tests run `kubectl kustomize`, plus one `kubectl patch --local`. No maintained Python kustomize exists, so the renders stay real, as decided on #1725 on 2026-10-20.

## Description

- [x] `docs/TESTING.md` and ADR 0007 list kubectl's offline renderers, `kubectl kustomize` and `kubectl patch --local`, with git as programs tests run for real. They read only files and reach no cluster.
- [x] `tests/k8s_manifests.py` renders each committed kustomization under `k8s/` once per test process, keyed by its resolved directory, and shares the render. A kustomization a test builds under `tmp_path` renders per call.
  - The Argo CD application, network policy and monitoring invariants and the overrides test read their renders through it.
  - `tests/test_k8s_argocd_apps.py` parses them with libyaml's `CSafeLoader`.
  - Every assertion is kept.
- [x] Measured on the 33 tests, alternating before and after runs at load 10-19:
  - serially: 17.6s to 12.8s wall;
  - at `-n 4`: 19.9s to 14.8s wall;
  - the nine repository-render tests other than the Argo CD gate test, serially: 7.3s to 2.5s.
- The Argo CD gate test renders inside devops-cli's own `run_subprocess`, so it can't share the render without patching devops-cli. It stays at about 2s.
