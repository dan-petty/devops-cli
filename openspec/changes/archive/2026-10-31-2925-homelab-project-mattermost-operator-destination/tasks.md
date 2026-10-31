# Tasks

## 1. Permit operator and system namespaces in homelab project destinations

- [x] 1.1 Add failing invariant test asserting AppProject `homelab` includes `mattermost-operator` and `cnpg-system` in its destination list in `tests/invariants/test_k8s_argocd_apps.py`. Verification: `uv run pytest tests/invariants/test_k8s_argocd_apps.py -k test_homelab_project_destinations`
- [x] 1.2 Add `mattermost-operator` and `cnpg-system` to the `destinations` of `homelab` in `k8s/argocd/apps/projects.yaml`. Verification: `uv run pytest tests/invariants/test_k8s_argocd_apps.py -k test_homelab_project_destinations`
- [x] 1.3 Verify all invariant tests pass. Verification: `uv run pytest tests/invariants/test_k8s_argocd_apps.py`

## Workflow follow-up

- Archive the change after implementation and checks pass.
