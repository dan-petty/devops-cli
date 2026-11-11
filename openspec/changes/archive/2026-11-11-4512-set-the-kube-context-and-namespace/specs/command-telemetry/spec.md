## ADDED Requirements

### Requirement: A devops-cli pod names its cluster and its namespace
Each devops-cli container in the render of `k8s/devops` SHALL set `K8S_CONTEXT` to the cluster name in `k8s/monitoring/k8s-monitoring-values.yaml` and `POD_NAMESPACE` to the namespace of its object. The tracer SHALL put the value of `K8S_CONTEXT` in the resource attribute `k8s.cluster.name` and the value of `POD_NAMESPACE` in the span attribute `k8s.namespace.name`.

#### Scenario: The manifests are rendered
- **WHEN** `kubectl kustomize k8s/devops` renders the Deployments, the CronJobs and the WorkflowTemplate
- **THEN** each devops-cli container sets `K8S_CONTEXT` to the cluster name of the monitoring stack, and `POD_NAMESPACE` from the Downward API, or as the plain value `devops` in the runner template

#### Scenario: A pod starts a span
- **WHEN** `K8S_CONTEXT` and `POD_NAMESPACE` are set and a span starts
- **THEN** the resource holds `k8s.cluster.name` with the value of `K8S_CONTEXT`, and the span holds `k8s.namespace.name` with the value of `POD_NAMESPACE`
