# Design

## Architecture

Mattermost Team Edition runs in namespace `mattermost`. It uses the official Mattermost Kubernetes Operator running in namespace `mattermost-operator`. PostgreSQL 17 is managed by the CloudNativePG operator in namespace `cnpg-system`.

```
Traefik Ingress (kube-system)
        │
        ▼ TCP 8065
Mattermost Pod (mattermost) ──▶ PostgreSQL Cluster (mattermost-db:5432)
        │                                  ▲
        ▼                                  │
Files PVC (mattermost-files)        CloudNativePG Operator (cnpg-system)
```

### Components

1. **Mattermost Operator**:
   - Deployed via Helm chart `mattermost-operator` version 1.0.5 in namespace `mattermost-operator`.
   - Managed with `ServerSideApply=true` due to CRD size limits.
   - Resource defaults enforced via `LimitRange`.

2. **CloudNativePG Operator**:
   - Deployed via Helm chart `cloudnative-pg` version 0.29.1 in namespace `cnpg-system`.
   - Managed with `ServerSideApply=true`.
   - PodMonitor and Grafana dashboard enabled.

3. **Mattermost Workload**:
   - Custom Resource `Mattermost` under `installation.mattermost.com/v1beta1`.
   - Recreate deployment strategy to prevent multiple pods mounting ReadWriteOnce volumes.
   - Local mode enabled for `mmctl` maintenance commands.
   - Telemetry, diagnostics, push notifications, and remote marketplace disabled.

4. **Network Isolation**:
   - Default perimeter in `mattermost` allows Ingress from Traefik on port 8065, intra-namespace traffic, CloudNativePG operator on ports 8000 and 5432, and Prometheus monitoring on port 9187.
   - Database API perimeter allows egress from PostgreSQL cluster pods to Kubernetes API server on ports 443 and 6443.
   - External public egress blocked; cloud metadata SSRF blocked.

## Rejected Alternatives

### 1. mattermost-team-edition Helm Chart
- *Alternative*: Deploy Mattermost using the `mattermost-team-edition` Helm chart.
- *Rejection Reason*: Upstream repository marks this chart unsupported and deprecated. It directs users to the Mattermost Operator.

### 2. Standalone PostgreSQL StatefulSet
- *Alternative*: Deploy a custom unmanaged PostgreSQL StatefulSet.
- *Rejection Reason*: Lacks automated minor version upgrades, automated failover, native Prometheus exporter, and Barman Cloud backup capabilities.

### 3. Placing `chat` in `_KUSTOMIZATIONS_BY_STACK`
- *Alternative*: Apply `k8s/mattermost` before Helm releases using `_KUSTOMIZATIONS_BY_STACK`.
- *Rejection Reason*: A native deploy executes `_KUSTOMIZATIONS_BY_STACK` before Helm chart installation. The `Cluster`, `Mattermost`, and `PodMonitor` resources would fail to apply because their CRDs do not exist yet. Using `_POST_HELM_BY_STACK` applies them after the operators install the CRDs.

### 4. Push Notifications via Hosted Test Proxy
- *Alternative*: Enable push notifications for Team Edition.
- *Rejection Reason*: Team Edition push notifications route every notification through an external hosted test proxy. Owner Decision D6 explicitly turned off push notifications to maintain zero public egress.
