# Tasks

## 1. Configure container security context for mattermost

- [x] 1.1 Add failing invariant test in `tests/invariants/test_k8s_argocd_apps.py` asserting `mattermost.yaml` specifies containerSecurityContext. Verification: `uv run pytest tests/invariants/test_k8s_argocd_apps.py -k test_mattermost_container_security_context`
- [x] 1.2 Add `containerSecurityContext` to `podTemplate` in `k8s/mattermost/mattermost.yaml`. Verification: `uv run pytest tests/invariants/test_k8s_argocd_apps.py -k test_mattermost_container_security_context`
- [x] 1.3 Verify all invariant tests pass. Verification: `uv run pytest tests/invariants/test_k8s_argocd_apps.py`

## Workflow follow-up

- Archive the change after implementation and checks pass.
