## MODIFIED Requirements

### Requirement: A devops-cli pod names its cluster and its namespace
Each devops-cli container in the render of `k8s/devops` SHALL set `K8S_CONTEXT` to one cluster name, the same in each container, and `POD_NAMESPACE` to the namespace of its object. The tracer SHALL put the value of `K8S_CONTEXT` in the resource attribute `k8s.cluster.name` and the value of `POD_NAMESPACE` in the span attribute `k8s.namespace.name`.

#### Scenario: The manifests are rendered
- **WHEN** `kubectl kustomize k8s/devops` renders the Deployments, the CronJobs and the WorkflowTemplates
- **THEN** each devops-cli container sets `K8S_CONTEXT` to the same cluster name, and `POD_NAMESPACE` from the Downward API, or as the plain value `devops` in the runner template

#### Scenario: A pod starts a span
- **WHEN** `K8S_CONTEXT` and `POD_NAMESPACE` are set and a span starts
- **THEN** the resource holds `k8s.cluster.name` with the value of `K8S_CONTEXT`, and the span holds `k8s.namespace.name` with the value of `POD_NAMESPACE`

## REMOVED Requirements

### Requirement: Loki datasource configures derived trace link to Tempo
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The collector deletes the host name of devops-cli metrics before it adds the deltas
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Two metric streams in one Prometheus series fire an alert
**Reason**: The environment repository holds this alert rule and its cases (#7290).
**Migration**: Change the rule in the environment repository.

### Requirement: One stream and a short overlap stay quiet
**Reason**: The environment repository holds this alert rule and its cases (#7290).
**Migration**: Change the rule in the environment repository.

### Requirement: The alert selects only a served series
**Reason**: The environment repository holds this alert rule and its cases (#7290).
**Migration**: Change the rule in the environment repository.

### Requirement: The rule set, the case file and the runbook list the alert
**Reason**: The alert is a rule of the environment repository (#7290). The rule for the cells of the Alerting table moves.
**Migration**: See `Each row of the Alerting table fits its header` of `product-monitoring-content`.
