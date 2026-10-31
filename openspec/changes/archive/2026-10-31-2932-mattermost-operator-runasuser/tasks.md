# Tasks

## 1. Configure numeric user identifiers for mattermost-operator

- [x] 1.1 Add failing invariant test in `tests/invariants/test_k8s_argocd_apps.py` asserting `mattermost-operator-values.yaml` specifies numeric user and group IDs. Verification: `uv run pytest tests/invariants/test_k8s_argocd_apps.py -k test_mattermost_operator_run_as_user`
- [x] 1.2 Add `runAsUser: 65532` and `runAsGroup: 65532` to `podSecurityContext` in `k8s/mattermost/mattermost-operator-values.yaml`. Verification: `uv run pytest tests/invariants/test_k8s_argocd_apps.py -k test_mattermost_operator_run_as_user`
- [x] 1.3 Verify all invariant tests pass. Verification: `uv run pytest tests/invariants/test_k8s_argocd_apps.py`

## Workflow follow-up

- Archive the change after implementation and checks pass.
