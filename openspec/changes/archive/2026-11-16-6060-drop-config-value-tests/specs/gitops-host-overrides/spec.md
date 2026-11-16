## MODIFIED Requirements

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
- **WHEN** the kube-state-metrics of the cluster serve `kube_ingress_path`
- **THEN** `kube_ingress_path` is in `clusterMetrics.kube-state-metrics.metricsTuning.includeMetrics` of `k8s/monitoring/k8s-monitoring-values.yaml`
- **AND** the series has the labels `host`, `ingress` and `namespace`
