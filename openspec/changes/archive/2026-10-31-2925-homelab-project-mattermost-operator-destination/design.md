# Design

## Context

See proposal.md - Why.
The Argo CD Application `base` resides in AppProject `homelab` and reconciles `k8s/kustomization.yaml`. Because `k8s/kustomization.yaml` renders `LimitRange/mattermost-operator-limits` in namespace `mattermost-operator`, Argo CD requires `mattermost-operator` to be an allowed destination in AppProject `homelab`.

## Goals / Non-Goals

**Goals:**
- Permit `mattermost-operator` and `cnpg-system` in `AppProject` `homelab` destinations.
- Add an invariant test ensuring that all namespaces referenced by resources in `base` are allowed destinations in `homelab`.

**Non-Goals:**
- Moving `mattermost-operator-limitrange.yaml` to a different kustomization directory.
- Modifying other AppProject permissions or cluster resource whitelists.

## Decisions

### D1: Add `mattermost-operator` and `cnpg-system` to `homelab` destinations in `projects.yaml`
- **Choice**: Add entries for `https://kubernetes.default.svc` with `namespace: mattermost-operator` and `namespace: cnpg-system` under `AppProject` `homelab` in `k8s/argocd/apps/projects.yaml`.
- **Rationale**: Application `base` renders namespaced resources into `mattermost-operator`. Both `cnpg-system` and `mattermost-operator` are managed alongside `mattermost` as part of the chat stack infrastructure.
- **Alternative considered**: Move `mattermost-operator-limits` to Helm chart values or another application.
  - *Evidence rejecting alternative*: Invariant test `test_mattermost_operator_limitrange` in `tests/invariants/test_k8s_argocd_apps.py` explicitly asserts that `mattermost-operator-limitrange.yaml` is in `k8s/kustomization.yaml`.

### D2: Assert destination coverage in invariant tests
- **Choice**: Update `tests/invariants/test_k8s_argocd_apps.py` to assert that `homelab` includes `mattermost-operator` and `cnpg-system` in its destination list.
- **Rationale**: Invariant tests gate CI and prevent regressions in GitOps project boundaries.

## Risks / Trade-offs

- [Broader destination scope in homelab project] → Low risk. The homelab AppProject already manages user-facing and platform services across 12 namespaces. Applications remain pinned to their specific target repositories and source paths.
