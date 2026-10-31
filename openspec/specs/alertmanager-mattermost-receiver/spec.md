# alertmanager-mattermost-receiver Specification

## Purpose
Configures Alertmanager to send critical and warning alerts to Mattermost's alerts channel using native Mattermost receiver integration.

## Requirements

### Requirement: Alertmanager sends alerts to Mattermost
Alertmanager SHALL route critical and warning alerts to receiver `mattermost`. Receiver `mattermost` SHALL define one `mattermost_configs` entry with `webhook_url_file: /etc/alertmanager-mattermost/url`, `send_resolved: true`, default templates, and empty `title_link`. The receiver SHALL NOT set `channel` or `username`.

#### Scenario: Critical and warning alerts route to Mattermost
- **WHEN** Alertmanager configuration is evaluated
- **THEN** routes with severity matching `critical|warning` route to receiver `mattermost`
- **AND** receiver `mattermost` has `webhook_url_file: /etc/alertmanager-mattermost/url` and `send_resolved: true`

#### Scenario: Unrouted alerts route to null
- **WHEN** an alert with severity other than critical or warning arrives
- **THEN** Alertmanager routes the alert to receiver `null`

### Requirement: Alertmanager mounts Mattermost webhook Secret
Alertmanager `extraSecretMounts` SHALL mount Secret `alertmanager-mattermost` at mount path `/etc/alertmanager-mattermost` as an optional, read-only volume.

#### Scenario: Optional secret mount configuration
- **WHEN** Alertmanager subchart values are inspected
- **THEN** `extraSecretMounts` contains an entry for `secretName: alertmanager-mattermost`
- **AND** `readOnly` is true and `optional` is true

### Requirement: Self-health alert watches Mattermost secret
Alert `AlertmanagerNotificationsFailing` SHALL select `kube_secret_info{namespace="monitoring", secret="alertmanager-mattermost"}` so that it evaluates only when the Mattermost webhook Secret exists.

#### Scenario: Alert rule selector requires Secret existence
- **WHEN** Prometheus alert rules are evaluated
- **THEN** `AlertmanagerNotificationsFailing` joins on `kube_secret_info` for secret `alertmanager-mattermost`

### Requirement: Network policies allow Alertmanager to Mattermost traffic
The `monitoring` namespace network policy SHALL allow egress to namespace `mattermost` on TCP port 8065. The `mattermost` namespace network policy SHALL allow ingress on TCP port 8065 exclusively from Alertmanager pods in namespace `monitoring`.

#### Scenario: Monitoring egress to Mattermost
- **WHEN** network policies in namespace `monitoring` are evaluated
- **THEN** egress to namespace `mattermost` on TCP port 8065 is permitted

#### Scenario: Mattermost ingress admits Alertmanager pods
- **WHEN** network policies in namespace `mattermost` are evaluated
- **THEN** ingress on TCP port 8065 from namespace `monitoring` requires pod label `app.kubernetes.io/name: alertmanager`
