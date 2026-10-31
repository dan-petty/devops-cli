# Tasks

## 1. Namespaces, LimitRange and Argo CD Applications
- [x] Add failing tests for namespaces, operator LimitRange, AppProjects, and Applications (`tests/invariants/test_k8s_argocd_apps.py`). Verification: `uv run pytest tests/invariants/test_k8s_argocd_apps.py`
- [x] Add namespaces `mattermost`, `cnpg-system`, `mattermost-operator` in `k8s/namespaces.yaml`, LimitRange in `k8s/mattermost-operator-limitrange.yaml`, and reference it in root `k8s/kustomization.yaml`. Verification: `uv run pytest tests/invariants/test_k8s_argocd_apps.py`
- [x] Update `k8s/argocd/apps/projects.yaml` for `homelab-system` and `homelab`. Add Applications `cloudnative-pg.yaml`, `mattermost-operator.yaml`, and `mattermost.yaml` in `k8s/argocd/apps/`. Update `k8s/argocd/bootstrap/cluster.yaml`. Verification: `uv run pytest tests/invariants/test_k8s_argocd_apps.py`
- [x] Regenerate documentation. Verification: `uv run devops docs generate --sync-readme`

## 2. Mattermost Stack Manifests and Values
- [x] Add failing tests for Mattermost custom resources, database, volume claims, telemetry settings, and network perimeters (`tests/commands/k8s/test_k8s_mattermost.py`, `tests/core/test_third_party_telemetry.py`, `tests/commands/k8s/test_k8s_network_policies.py`). Verification: `uv run pytest tests/commands/k8s/test_k8s_mattermost.py tests/core/test_third_party_telemetry.py tests/commands/k8s/test_k8s_network_policies.py`
- [x] Create `k8s/mattermost/cloudnative-pg-values.yaml` and `k8s/mattermost/mattermost-operator-values.yaml`. Verification: `uv run pytest tests/commands/k8s/test_k8s_mattermost.py`
- [x] Create `k8s/mattermost/database.yaml`, `k8s/mattermost/files-pvc.yaml`, `k8s/mattermost/mattermost.yaml`, `k8s/mattermost/podmonitor.yaml`, `k8s/mattermost/networkpolicy.yaml`, and `k8s/mattermost/kustomization.yaml`. Verification: `uv run pytest tests/commands/k8s/test_k8s_mattermost.py tests/core/test_third_party_telemetry.py tests/commands/k8s/test_k8s_network_policies.py`
- [x] Regenerate documentation. Verification: `uv run devops docs generate --sync-readme`

## 3. CLI Stack Lifecycle and Cluster Secrets Push Table
- [x] Add failing tests for `chat` stack definitions, host overrides, and `mattermost/mattermost-db` secret push (`tests/k8s/test_k8s_argocd_overrides.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/k8s/test_cluster_secret_push.py`). Verification: `uv run pytest tests/k8s/test_k8s_argocd_overrides.py tests/k8s/test_cluster_secret_plan.py tests/k8s/test_cluster_secret_push.py`
- [x] Add `chat` to `CONST_K8S_STACKS`, `mattermost` to `CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS` and `CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS_BY_STACK` in `src/devops_cli/config/constants.py`. Update `_host_fields` in `src/devops_cli/k8s/argocd_overrides.py`. Verification: `uv run pytest tests/k8s/test_k8s_argocd_overrides.py`
- [x] Register `chat` in `HELM_REPOS_BY_STACK`, `HELM_RELEASES_BY_STACK`, and `_POST_HELM_BY_STACK` in `src/devops_cli/commands/k8s/stack_lifecycle.py`. Verification: `uv run pytest tests/commands/k8s/test_k8s_mattermost.py`
- [x] Add `mattermost/mattermost-db` row to `CLUSTER_SECRETS` in `src/devops_cli/k8s/cluster_secrets.py`. Verification: `uv run pytest tests/k8s/test_cluster_secret_plan.py tests/k8s/test_cluster_secret_push.py`
- [x] Regenerate documentation. Verification: `uv run devops docs generate --sync-readme`

## 4. Monitoring Alerts, README and CI Verification
- [x] Add failing tests for Mattermost alert rules in `tests/prometheus/test_k8s_monitoring_alerting.py`. Verification: `uv run pytest tests/prometheus/test_k8s_monitoring_alerting.py`
- [x] Add `MattermostUnavailable` and `MattermostDatabaseDown` alerts to `k8s/monitoring/prometheus-values.yaml`. Update `k8s/monitoring/networkpolicy.yaml` egress rules. Add `cnpg_collector_up` to `SERVED_SERIES` in `test_k8s_monitoring_alerting.py`. Verification: `uv run pytest tests/prometheus/test_k8s_monitoring_alerting.py`
- [x] Add Mattermost guide section and tunnel diagram update in `k8s/README.md`. Verification: `uv run pytest tests/invariants/test_architectural_invariants.py`
- [x] Regenerate documentation. Verification: `uv run devops docs generate --sync-readme`
- [x] Run full test suite and CI checks. Verification: `uv run devops ci`

## Workflow follow-up
- Configure Mattermost push notifications and marketplace if approved in a future change (#1391).
- CloudNativePG database backups via Barman Cloud (#1081).
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
