# gitops-host-overrides Specification

## Purpose
Which hosts and container environment values the deploy-time overrides set on the homelab Argo CD Applications, how the overrides stay in place through a sync of the app-of-apps `cluster`, and the alert that fires when a live Ingress routes a host under the placeholder domain of git.

## Requirements

### Requirement: Open WebUI allows only the origins of its Ingress hosts
Open WebUI SHALL read `CORS_ALLOW_ORIGIN` from ConfigMap `llm/open-webui-origins`, through a `configMapRef` in `extraEnvFrom` of `k8s/llm/values-open-webui.yaml` that is not optional. The Application `ingress` SHALL render the ConfigMap. Its value SHALL be the HTTPS origin of each host of Ingress `llm/open-webui-ingress`, in the order of the rules, separated by `;`.

#### Scenario: The origins follow the Ingress hosts
- **WHEN** the `k8s` row of `devops ci` renders the Application `ingress`
- **THEN** `CORS_ALLOW_ORIGIN` of ConfigMap `llm/open-webui-origins` is the HTTPS origin of each host of Ingress `llm/open-webui-ingress`
- **AND** `extraEnvFrom` of `k8s/llm/values-open-webui.yaml` holds `{configMapRef: {name: open-webui-origins}}`

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

### Requirement: The Argo CD gate permits the placeholder only in host fields
The Argo CD gate SHALL permit the placeholder domain only in the host fields of the Applications `devops`, `ingress` and `mattermost`: the hosts of an Ingress, an IngressRoute and a Mattermost, each container `env[].value` of a Deployment, and each `data` value of a ConfigMap. The infra repo sets the real values with Kustomize patches of the Application.

#### Scenario: A Deployment holds the placeholder in an env value and in an argument
- **WHEN** the Application `devops` renders a Deployment with the placeholder in an env value and in an argument
- **THEN** the gate refuses only the argument

#### Scenario: A ConfigMap holds the placeholder in a data value and in an annotation
- **WHEN** the Application `devops` renders a ConfigMap with the placeholder in a data value and in an annotation
- **THEN** the gate refuses only the annotation

### Requirement: deploy-stack writes no Application override
On a cluster that Argo CD manages, `devops k8s deploy-stack` SHALL NOT patch an Argo CD Application, and SHALL NOT need a domain.

#### Scenario: Deploy of the infra stack
- **WHEN** `deploy-stack --stack infra` runs with no domain on a cluster that Argo CD manages
- **THEN** it exits 0 and writes no object
