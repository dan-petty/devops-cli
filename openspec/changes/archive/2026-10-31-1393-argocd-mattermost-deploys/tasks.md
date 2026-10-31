# Tasks

## 1. Network Policies

- [x] 1.1 Write failing tests in `tests/commands/k8s/test_k8s_network_policies.py` asserting `argocd` egress to `mattermost` on TCP port 8065 and `mattermost` ingress admitting `argocd-notifications-controller` on TCP port 8065. Verify with `uv run pytest tests/commands/k8s/test_k8s_network_policies.py`.
- [x] 1.2 Implement egress in `k8s/argocd/networkpolicy.yaml` and ingress in `k8s/mattermost/networkpolicy.yaml`. Verify with `uv run pytest tests/commands/k8s/test_k8s_network_policies.py tests/commands/k8s/test_k8s_mattermost.py`.
- [x] 1.3 Sync documentation with `uv run devops docs generate --sync-readme`.

## 2. Secrets and Credentials

- [x] 2.1 Write failing unit tests for credential `mattermost.deploys_hook` and derived key `mattermost-deploys-url` in `tests/k8s/test_cluster_secret_plan.py` and `tests/security/test_config_declarations.py`. Verify with `uv run pytest tests/k8s/test_cluster_secret_plan.py tests/security/test_config_declarations.py`.
- [x] 2.2 Add `mattermost.deploys_hook` to `CREDENTIALS` in `src/devops_cli/config/env.py` and derived key `mattermost-deploys-url` to `argocd/argocd-notifications-secret` in `src/devops_cli/k8s/cluster_secrets.py`. Verify with `uv run pytest tests/k8s/test_cluster_secret_plan.py tests/security/test_config_declarations.py tests/commands/test_config_audit_keys.py tests/commands/k8s/test_k8s.py`.
- [x] 2.3 Sync documentation with `uv run devops docs generate --sync-readme`.

## 3. Argo CD Notifications Configuration

- [x] 3.1 Write failing tests in `tests/test_k8s_argocd_apps.py` asserting notifications controller settings, webhook notifier configuration, templates using `toJson`, global `on-sync-failed` subscription, and `on-deployed` annotation on application `devops`. Verify with `uv run pytest tests/test_k8s_argocd_apps.py`.
- [x] 3.2 Update `k8s/argocd/values.yaml` with notifications controller configuration, webhook notifier, catalog triggers, JSON templates, and global subscription. Add subscription annotation to `k8s/argocd/apps/devops.yaml`. Verify with `uv run pytest tests/test_k8s_argocd_apps.py tests/invariants/test_k8s_manifests.py`.
- [x] 3.3 Sync documentation with `uv run devops docs generate --sync-readme`.

## 4. Documentation and Final Verification

- [x] 4.1 Update `k8s/README.md` with Notifications subsection detailing webhook creation, configuration commands, push-secrets behavior, and notification scopes. Verify with `uv run pytest tests/invariants/test_k8s_manifests.py`.
- [x] 4.2 Sync documentation with `uv run devops docs generate --sync-readme`.
- [x] 4.3 Verify full CI suite and OpenSpec compliance with `uv run devops openspec check` and `uv run devops ci`.

## Workflow follow-up

- Archive change 1393-argocd-mattermost-deploys.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
