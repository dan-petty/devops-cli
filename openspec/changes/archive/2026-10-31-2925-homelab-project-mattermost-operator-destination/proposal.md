# Proposal

## Why

Issue #2925 addresses a failure in the Argo CD `base` application where destination namespace `mattermost-operator` is rejected in `AppProject` `homelab`. This prevents cluster namespaces from being created, blocking the deployment of `mattermost`, `mattermost-operator`, and `cloudnative-pg`.

## What Changes

- Add `namespace: mattermost-operator` and `namespace: cnpg-system` to the destination list of `AppProject` `homelab` in `k8s/argocd/apps/projects.yaml`.
- Add test assertions in `tests/invariants/test_k8s_argocd_apps.py` ensuring `homelab` permits destination namespaces required by the `base` application.

## Capabilities

### New Capabilities

- `homelab-project-destinations`: AppProject `homelab` permits destination namespaces `mattermost-operator` and `cnpg-system` so that Application `base` can manage resources in these namespaces.

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/argocd/apps/projects.yaml`.
- Tests: `tests/invariants/test_k8s_argocd_apps.py`.
- Fits in one pull request.

## Feasibility

Confirmed against the real system:
- `kubectl get application -n argocd base` failed with `one or more synchronization tasks are not valid: namespace mattermost-operator is not permitted in project 'homelab'`.
- Argo CD project destination boundaries enforce that any namespaced resource managed by an application must target a namespace declared in the project's `destinations` list.
- Adding `mattermost-operator` and `cnpg-system` to `homelab`'s `destinations` satisfies Argo CD project destination validation.

## Existing Tool Considered

Argo CD `AppProject` destination access controls. The cluster uses Argo CD AppProjects (`homelab` and `homelab-system`) to partition access and scope. Updating the destination list in `projects.yaml` aligns permissions with the resources rendered by `k8s/kustomization.yaml`.
