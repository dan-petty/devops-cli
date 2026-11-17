## REMOVED Requirements

### Requirement: The app-of-apps applies the homelab Applications server-side
**Reason**: Its scenario named a test that reads the Application manifests. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with a live check (#6083).
**Migration**: The requirement "Argo CD applies three homelab Applications server-side" holds the same rule.

### Requirement: An Ingress that routes a placeholder host alerts
**Reason**: Its scenario named a test that reads the alert rule. OpenSpec keeps each scenario name of a MODIFIED requirement, so the rule comes back under a new name with live checks (#6083).
**Migration**: The requirement "An Ingress with a placeholder host fires an alert" holds the same rule.

## ADDED Requirements

### Requirement: Argo CD applies three homelab Applications server-side
The Applications `devops`, `ingress` and `mattermost` in `k8s/argocd/apps/` SHALL have `ServerSideApply=true` in their `argocd.argoproj.io/sync-options` annotation, and no other Application SHALL have it. The Application `cluster` SHALL have the annotation `argocd.argoproj.io/client-side-apply-migration-manager` with the value `argocd-controller`.

#### Scenario: The field managers of the Applications
- **WHEN** Argo CD syncs Application `cluster`, and a person runs `kubectl -n argocd get applications --show-managed-fields -o yaml`
- **THEN** the field manager `argocd-controller` holds an `Apply` entry on `devops`, `ingress` and `mattermost`, and on no other Application
- **AND** the sync of `cluster` reports no field conflict

### Requirement: An Ingress with a placeholder host fires an alert
The alert rule `IngressServesPlaceholderHost` in the group `homelab-services` of `k8s/monitoring/prometheus-values.yaml` SHALL fire at severity `critical` after 5 minutes for each Ingress that has a `kube_ingress_path` series with a host under the placeholder domain `example.com`. The kube-state-metrics `includeMetrics` in `k8s/monitoring/k8s-monitoring-values.yaml` SHALL keep `kube_ingress_path`.

#### Scenario: Prometheus loads the rule
- **WHEN** a person runs `uv run devops prometheus rules`
- **THEN** the group `homelab-services` holds the alerting rule `IngressServesPlaceholderHost` with the health `ok`

#### Scenario: A deploy that sets every host keeps the alert quiet
- **WHEN** a deploy sets the host of each Ingress to the configured domain, and a person runs `uv run devops prometheus query 'ALERTS{alertname="IngressServesPlaceholderHost"}'`
- **THEN** the query returns no series

#### Scenario: The series reaches Prometheus
- **WHEN** a person runs `uv run devops prometheus query 'kube_ingress_path'`
- **THEN** the query returns a series for each Ingress of the cluster, and each series has the labels `host`, `ingress` and `namespace`
