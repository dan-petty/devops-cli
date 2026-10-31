# Tasks

## 1. Network Policies

- [x] 1.1 Write failing tests in `tests/commands/k8s/test_k8s_network_policies.py` for monitoring egress to namespace `mattermost` on TCP 8065 and mattermost ingress admitting Alertmanager pods; verify with `uv run pytest tests/commands/k8s/test_k8s_network_policies.py`.
- [x] 1.2 Add egress rule to namespace `mattermost` on TCP 8065 in `k8s/monitoring/networkpolicy.yaml` and ingress rule admitting Alertmanager pods on TCP 8065 in `k8s/mattermost/networkpolicy.yaml`; verify with `uv run pytest tests/commands/k8s/test_k8s_network_policies.py`.

## 2. Secrets and Push Table

- [x] 2.1 Write failing tests in `tests/invariants/test_k8s_manifests.py` and `tests/k8s/test_cluster_secret_plan.py` for `secretName` extraction in `_secret_references`, managed credential `mattermost.alerts_hook`, and `monitoring/alertmanager-mattermost` push row; verify with `uv run pytest tests/invariants/test_k8s_manifests.py tests/k8s/test_cluster_secret_plan.py`.
- [x] 2.2 Add `mattermost.alerts_hook` to `CREDENTIALS` in `src/devops_cli/config/env.py`, add `monitoring/alertmanager-mattermost` to `CLUSTER_SECRETS` in `src/devops_cli/k8s/cluster_secrets.py`, ignore orphan Secret `alertmanager-mattermost` in `k8s/argocd/apps/projects.yaml`, and update `_secret_references` in `tests/invariants/test_k8s_manifests.py`; verify with `uv run pytest tests/invariants/test_k8s_manifests.py tests/k8s/test_cluster_secret_plan.py`.

## 3. Alertmanager Values and Monitoring Alerts

- [x] 3.1 Write failing tests in `tests/prometheus/test_k8s_monitoring_alerting.py` for `mattermost` receiver, `alertmanager-mattermost` mount, `AlertmanagerNotificationsFailing` secret selector, and `RoadmapServiceJobsFailing` grouping and Loki description; verify with `uv run pytest tests/prometheus/test_k8s_monitoring_alerting.py`.
- [x] 3.2 Update `k8s/monitoring/prometheus-values.yaml` to configure `mattermost` receiver, mount Secret `alertmanager-mattermost`, update `AlertmanagerNotificationsFailing`, and update `RoadmapServiceJobsFailing`; verify with `uv run pytest tests/prometheus/test_k8s_monitoring_alerting.py`.
- [x] 3.3 Update `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml` to align promtool unit tests with updated `RoadmapServiceJobsFailing` alert rule; verify with `uv run pytest tests/prometheus/test_k8s_monitoring_alerting.py`.

## 4. Documentation and Cleanup

- [x] 4.1 Update `k8s/README.md` Receiver section with the three-step wiring instructions, remove `kubectl create secret`, and update the alert table; verify with `uv run devops docs generate --sync-readme`.
- [x] 4.2 Verify no occurrences of `alertmanager-webhook` remain in `k8s/` or `tests/`; verify with `git grep "alertmanager-webhook" k8s/ tests/`.

## 5. Verification and Quality Gates

- [x] 5.1 Run full quality gates and verify `uv run devops ci` passes.
- [x] 5.2 Archive OpenSpec change with `uv run devops openspec archive 1392-alertmanager-mattermost-alerts`.

## Workflow follow-up

- Pending a person: after merge, wire the incoming webhook in Mattermost `alerts` channel and verify alert delivery.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
