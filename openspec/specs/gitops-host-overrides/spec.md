# gitops-host-overrides Specification

## Purpose
Which hosts and container environment values the deploy-time overrides set on the homelab Argo CD Applications, how the overrides stay in place through a sync of the app-of-apps `cluster`, and the alert that fires when a live Ingress routes a host under the placeholder domain of git.

## Requirements

### Requirement: The app-of-apps applies the homelab Applications server-side
The Applications `devops`, `ingress` and `mattermost` in `k8s/argocd/apps/` SHALL have `ServerSideApply=true` in their `argocd.argoproj.io/sync-options` annotation, and no other Application SHALL have it. The Application `cluster` SHALL have the annotation `argocd.argoproj.io/client-side-apply-migration-manager` with the value `argocd-controller`.

#### Scenario: A test reads the Application manifests
- **WHEN** a test reads `k8s/argocd/bootstrap/bootstrap.yaml`, `k8s/argocd/bootstrap/cluster.yaml` and each Application in `k8s/argocd/apps/`
- **THEN** the Applications with `ServerSideApply=true` in their sync-options annotation are `devops`, `ingress` and `mattermost` and no other
- **AND** `cluster` names `argocd-controller` as its client-side apply migration manager

### Requirement: An Ingress that routes a placeholder host alerts
The alert rule `IngressServesPlaceholderHost` in the group `homelab-services` of `k8s/monitoring/prometheus-values.yaml` SHALL fire at severity `critical` after 5 minutes for each Ingress that has a `kube_ingress_path` series with a host under the placeholder domain `example.com`. The kube-state-metrics `includeMetrics` in `k8s/monitoring/k8s-monitoring-values.yaml` SHALL keep `kube_ingress_path`.

#### Scenario: A test reads the rule
- **WHEN** a test reads the group `homelab-services`
- **THEN** `IngressServesPlaceholderHost` has the expression `count by (namespace, ingress) (kube_ingress_path{host=~"(.+\\.)?example\\.com"}) > 0`, `for: 5m` and severity `critical`

#### Scenario: The host pattern matches the hosts of git
- **WHEN** a test reads each Ingress in a YAML file under `k8s/`
- **THEN** the host pattern of the rule matches the host of each of their rules
- **AND** it does not match `argocd.example.org`, `example.com.example.net` or `notexample.com`

#### Scenario: The series reaches Prometheus
- **WHEN** a test reads `k8s/monitoring/k8s-monitoring-values.yaml` and the kube-state-metrics capture `tests/fixtures/metrics/kube-state-metrics.yaml`
- **THEN** `kube_ingress_path` is in `clusterMetrics.kube-state-metrics.metricsTuning.includeMetrics`
- **AND** the capture gives `kube_ingress_path` the labels `host`, `ingress` and `namespace`

### Requirement: deploy-stack sets the configured domain in container environment values
For each Deployment in the render of a homelab Application, `host_patches` SHALL test and then replace each `env[].value` of a container or init container that holds the placeholder domain. It SHALL change no other value, and the Argo CD gate SHALL allow the placeholder in such a value only.

#### Scenario: A Deployment holds the placeholder in three env values
- **WHEN** `host_patches` reads a Deployment with the placeholder in an init container value, two container values, an argument and an annotation, and with a value without it
- **THEN** the patch has a `test` and a `replace` operation for each of the three env values with the placeholder, and none for the argument, the annotation or the other value

#### Scenario: The Argo CD gate reads such a Deployment
- **WHEN** the Application `devops` renders a Deployment with the placeholder in an env value and in an argument
- **THEN** the gate refuses only the argument
