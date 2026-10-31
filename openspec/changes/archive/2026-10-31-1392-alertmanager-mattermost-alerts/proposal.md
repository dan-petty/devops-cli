# Proposal

## Why

Issue #1392 resolves failing Alertmanager notifications and missing alerts for failed roadmap Service runs. Today, every notification from Alertmanager fails because the configured webhook Secret does not exist, and Alertmanager cannot route alerts to Mattermost. Furthermore, no alert fires when all roadmap Service jobs for a repository and lane fail for an extended duration.

This change fits in one pull request.

## What Changes

- Replace the placeholder `webhook` receiver in `k8s/monitoring/prometheus-values.yaml` with native `mattermost` receiver using `mattermost_configs` (`webhook_url_file: /etc/alertmanager-mattermost/url`, `send_resolved: true`, empty `title_link`).
- Update `extraSecretMounts` in `prometheus-values.yaml` to mount Secret `alertmanager-mattermost` at `/etc/alertmanager-mattermost` as an optional, read-only volume.
- Update `AlertmanagerNotificationsFailing` alert rule to select `kube_secret_info` for Secret `alertmanager-mattermost`.
- Add `monitoring/alertmanager-mattermost` to the cluster secrets push table in `src/devops_cli/k8s/cluster_secrets.py` under stack `infra`. Derive `url` from `CONST_K8S_MATTERMOST_URL`, `/hooks/`, and managed credential `mattermost.alerts_hook`.
- Add managed credential `mattermost.alerts_hook` with keyring identifier `mattermost_alerts_hook` to `CREDENTIALS` in `src/devops_cli/config/env.py`.
- Ignore orphan Secret `alertmanager-mattermost` in `k8s/argocd/apps/projects.yaml`.
- Update `_secret_references` in `tests/invariants/test_k8s_manifests.py` to yield `secretName` values from volume mounts.
- Add network policy egress from namespace `monitoring` to namespace `mattermost` on TCP port 8065 in `k8s/monitoring/networkpolicy.yaml`.
- Add network policy ingress in namespace `mattermost` admitting TCP port 8065 traffic exclusively from Alertmanager pods in namespace `monitoring` in `k8s/mattermost/networkpolicy.yaml`.
- Update `RoadmapServiceJobsFailing` alert rule in `prometheus-values.yaml` to wait `for: 30m`, match on `(repo, lane)`, and alert when an hour has errors and zero successes.
- Update documentation in `k8s/README.md` for receiver wiring and alert catalog.

## Capabilities

### New Capabilities
- `alertmanager-mattermost-receiver`: Alertmanager sends critical and warning alerts to Mattermost's `alerts` channel through native `mattermost_configs`, reading the webhook URL from an optional mounted Secret and communicating across network policies over port 8065.

### Modified Capabilities
- `stack-credential-sync`: The cluster Secret push table includes `monitoring/alertmanager-mattermost` under stack `infra` with derived `url` from `mattermost.alerts_hook`, and secret reference validation inspects `secretName` fields.
- `roadmap-service-alerts`: `RoadmapServiceJobsFailing` alert waits `for: 30m`, groups and joins on `(repo, lane)` over a 1-hour window, and provides summary and Loki query description.

## Impact

- Manifests in `k8s/monitoring/` and `k8s/mattermost/`.
- Cluster secrets push table and configuration definitions in `src/devops_cli/`.
- Tests in `tests/prometheus/`, `tests/commands/k8s/`, and `tests/invariants/`.
- User documentation in `k8s/README.md`.

## Feasibility

- Alertmanager v0.34.1 supports `mattermost_configs` natively with `webhook_url_file`. Confirmed in upstream documentation (`docs/configuration.md`).
- Mattermost runs on Kubernetes in namespace `mattermost` listening on TCP port 8065. Confirmed in `k8s/mattermost/mattermost.yaml` and `CONST_K8S_MATTERMOST_URL`.
- Network policies allow egress and ingress on specified ports and pod selectors using standard Kubernetes NetworkPolicy v1.

## Existing Tool Considered

Alertmanager's native `mattermost_configs` integration is used directly instead of deploying an intermediate webhook converter or routing through custom services. This eliminates extra maintenance costs, runtime tokens, and intermediate failure points. Internal manual secret creation instructions with `kubectl` are deleted in favor of the automated `devops k8s push-secrets` command.
