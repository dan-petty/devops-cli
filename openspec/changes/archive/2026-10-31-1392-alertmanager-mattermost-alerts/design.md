# Design

## Context

See `proposal.md` for motivation. The Kubernetes cluster currently runs Alertmanager v0.34.1 in namespace `monitoring` and Mattermost in namespace `mattermost`. Alertmanager currently points critical and warning routes to an unconfigured webhook receiver whose Secret does not exist. Network policies between the `monitoring` and `mattermost` namespaces currently allow only PostgreSQL exporter traffic on port 9187. The roadmap Service exports metrics via annotation autodiscovery, but the current `RoadmapServiceJobsFailing` alert rule does not detect when all jobs for an hour fail.

## Goals / Non-Goals

**Goals:**
- Replace the legacy webhook receiver with native `mattermost_configs` in Alertmanager.
- Mount Secret `alertmanager-mattermost` optionally at `/etc/alertmanager-mattermost`.
- Add `monitoring/alertmanager-mattermost` to the cluster Secret push table under stack `infra`.
- Add managed credential `mattermost.alerts_hook` with keyring identifier `mattermost_alerts_hook`.
- Open network policy egress from `monitoring` to `mattermost` on port 8065, and admit only Alertmanager pods in `mattermost` ingress.
- Update `RoadmapServiceJobsFailing` to alert when an hour has errors and zero successes for a repository and lane after 30 minutes.

**Non-Goals:**
- Managing Alertmanager notification templates beyond default templates and empty `title_link`.
- Public egress from Alertmanager to external chat providers.
- Changing roadmap Service internal logic or lifting the `replicas: 0` hold from #1562.

## Decisions

### Decision 1: Use Alertmanager native `mattermost_configs`
Alertmanager v0.34.1 natively includes `mattermost_configs`, which reads `webhook_url_file` dynamically on each notification and formats alerts.
- *Alternative Considered*: Deploying a separate webhook converter service.
- *Evidence for Rejection*: A converter requires a separate deployment, resource budget, and network policy, adding maintenance cost and potential failure modes.

### Decision 2: Manage webhook Secret via `push-secrets` derived entry
Secret `alertmanager-mattermost` contains a single derived key `url` constructed from `CONST_K8S_MATTERMOST_URL`, `/hooks/`, and keyring entry `mattermost_alerts_hook`.
- *Alternative Considered*: Manual secret creation using `kubectl create secret`.
- *Evidence for Rejection*: Manual creation stores secrets in shell history, bypasses the cluster secret reference guard, and creates untracked cluster drift.

### Decision 3: Restrict network policy to Alertmanager pods on port 8065
The `mattermost` perimeter admits ingress on TCP port 8065 only from pods with label `app.kubernetes.io/name: alertmanager` in namespace `monitoring`.
- *Alternative Considered*: Permitting all pods in namespace `monitoring` to reach Mattermost on port 8065.
- *Evidence for Rejection*: Zero-trust network policy principles mandate least privilege; only Alertmanager needs HTTP access to Mattermost webhooks.

### Decision 4: Update `RoadmapServiceJobsFailing` to compare error and success rates
The alert evaluates `sum by (repo, lane) (increase(devops_cli_service_jobs_total{job="roadmap-service", result="error"}[1h])) > 0 unless on (repo, lane) sum by (repo, lane) (increase(devops_cli_service_jobs_total{job="roadmap-service", result="success"}[1h])) > 0` with `for: 30m`.
- *Alternative Considered*: Keeping `>= 3` errors threshold.
- *Evidence for Rejection*: Three errors can occur alongside normal successful jobs. The owner required alerts when a repository's jobs completely fail for an hour.

## Risks / Trade-offs

- [Risk]: Alertmanager crashes if the Secret mount is required but missing.
  → Mitigation: Mount Secret `alertmanager-mattermost` with `optional: true` and `readOnly: true`. Alertmanager starts normally and reads the file once created.
- [Risk]: Mattermost or database outage prevents alerts from reaching human operators.
  → Mitigation: Documented as an architectural limit in `k8s/README.md`. An external watchdog will be addressed in a subsequent roadmap item.

## Migration Plan

1. Apply updated network policies and Alertmanager configuration in `monitoring`.
2. Add cluster Secret table row and push `monitoring/alertmanager-mattermost` with `devops k8s push-secrets`.
3. Verify `AlertmanagerNotificationsFailing` stays quiet and test notifications arrive in the `alerts` channel.
