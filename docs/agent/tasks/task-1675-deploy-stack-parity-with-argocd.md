# Task: Deploy-stack parity with Argo CD Applications (#1675)

**Issue**: [#1675](https://github.com/dan-petty/devops-cli/issues/1675)
**Scope**: type/fix, scope/k8s
**Feasibility**: Verified against repository manifest definitions (`k8s/argocd/apps/`, `k8s/ingress/`, `k8s/llm/`, `k8s/gpu-feature-discovery/`) and the `stack_lifecycle.py` deployment pipeline. Confirmed via TDD that test assertions failed before the changes (RED) and passed cleanly after implementation (GREEN).

## Description

The `devops k8s deploy-stack --stack all` command and Argo CD Applications deployed different sets of Kubernetes manifests and charts, violating the invariant that `deploy-stack` comprehensively deploys all resources across stacks. Specifically, native `deploy-stack` omitted Traefik (`kube-system/traefik`), wildcard Ingress and IngressRoute definitions (`k8s/ingress/ingress-routes.yaml`), GPU feature discovery (`k8s/gpu-feature-discovery`), Portkey (`k8s/llm/portkey/*`), and the Valkey run index (`k8s/llm/valkey-runs.yaml`). Furthermore, tests masked these gaps via hand-injected map entries in `tests/test_k8s_argocd_apps.py` and undeployed policy exemptions in `tests/test_k8s_network_policies.py`.

This item closes all discrepancies and achieves full deployment parity:
- **Traefik Helm Release**: Added repository `traefik` (`https://traefik.github.io/charts`) to `_HELM_REPOS_BY_STACK["infra"]` and registered the pinned `traefik` Helm release (`traefik/traefik`, version 41.6.0, namespace `kube-system`, values `k8s/ingress/traefik-values.yaml`) in `_HELM_RELEASES_BY_STACK["infra"]`.
- **Traefik Conflict Guard**: In `_adopt_helm_resource_if_conflict`, guarded against adopting pre-existing conflicting resources for the `traefik` release, warning that stock k3s must be run with `--disable traefik` rather than adopting resources.
- **GPU Feature Discovery**: Added `Path("gpu-feature-discovery")` to `_KUSTOMIZATIONS_BY_STACK["infra"]`.
- **Ingress Routes Manifest**: Added `DEFAULT_K8S_DIR / "ingress" / "ingress-routes.yaml"` to `_MANIFESTS_BY_STACK["infra"]`, ensuring domain substitution applies during native deployment.
- **Portkey & Valkey Runs Manifests**: Added `k8s/llm/valkey-runs.yaml` and `k8s/llm/portkey/{configmap,deployment,service,networkpolicy}.yaml` to `_MANIFESTS_BY_STACK["llm"]`.
- **Tests & Invariant Enforcement**:
  - Dropped `UNDEPLOYED_NETWORK_POLICIES` exemptions in `tests/test_k8s_network_policies.py`.
  - Replaced the hand-injected Traefik release map in `test_helm_sources_pinned_versions` with an exhaustive `test_every_application_in_argocd_apps_maps_to_deploy_stack_counterpart` mapping every Application in `k8s/argocd/apps` (excluding `argocd-image-updater`) to its deploy-stack counterpart.
  - Added unit test `test_adopt_helm_resource_warns_and_refuses_for_traefik` in `tests/test_k8s.py`.
  - Updated expected dry-run kustomizations in `test_deploy_stack_dry_run_lists_the_kustomizations_its_stacks_apply` and `test_deploy_stack_applies_kustomizations`.
- **Documentation**: Updated `k8s/README.md` to document that `valkey-runs` and Ingress routes are deployed by `deploy-stack`, and noted that k3s must run with `--disable traefik`.

## Acceptance Criteria

- [x] `tests/test_k8s_network_policies.py` dropped all exemptions in `UNDEPLOYED_NETWORK_POLICIES` and passes.
- [x] `tests/test_k8s_argocd_apps.py` removed hand-injected Traefik mapping and verifies that every Application in `k8s/argocd/apps` maps to a deploy-stack counterpart.
- [x] `_adopt_helm_resource_if_conflict` warns and returns `False` when release name is `traefik`.
- [x] `_HELM_REPOS_BY_STACK`, `_HELM_RELEASES_BY_STACK`, `_KUSTOMIZATIONS_BY_STACK`, and `_MANIFESTS_BY_STACK` in `stack_lifecycle.py` include all missing counterparts.
- [x] `k8s/README.md` documents `valkey-runs` and Ingress route deployment by `deploy-stack` and k3s `--disable traefik`.
- [x] All test suites and quality gates pass locally (`uv run devops ci`).
- [x] `changelog.d/1675.md`.

## Deliverables

- [x] `src/devops_cli/commands/k8s/stack_lifecycle.py`
- [x] `tests/test_k8s_network_policies.py`
- [x] `tests/test_k8s_argocd_apps.py`
- [x] `tests/test_k8s.py`
- [x] `k8s/README.md`
- [x] `changelog.d/1675.md`
- [x] `docs/agent/tasks/task-1675-deploy-stack-parity-with-argocd.md`
