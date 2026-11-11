# Design

## Decisions

- **Environment values, no code.** The tracer already reads `K8S_CONTEXT` and `POD_NAMESPACE` first. A value in each pod spec corrects the name, and the workstation keeps the setting `k8s.context`.
- **The cluster name of the monitoring stack.** The metrics of Alloy name the cluster `homelab-k3s` (`cluster.name` in `k8s/monitoring/k8s-monitoring-values.yaml`), and the collector writes the same `cluster` label. The spans use the same name, so a query can join the two. The check reads the name from that file, so the two cannot differ.
- **The namespace from the Downward API.** The standard way to give a pod its namespace. The runner template sets the plain value `devops`, because the admission policy `roadmap-service-jobs` refuses `valueFrom` in a Job of the Service. The check holds the plain value equal to the namespace of the CronJob.
- **A check of the render.** A manifest gets no pytest test (docs/TESTING.md). The check of the `k8s` row reads the render that Argo CD applies and lists the 5 devops-cli containers by name, so a new devops-cli container without the values fails it.
- **A test of the names.** The check holds the manifests, and the test holds the tracer to the same two names.

## Rejected alternatives

- **The Downward API in the runner template too.** Rejected: the admission policy refuses `valueFrom` in a Job of the Service, and the check `job_admission_policy` fails on it. To allow `fieldRef` in the policy would weaken a security control for one label.
- **`OTEL_RESOURCE_ATTRIBUTES` with `k8s.cluster.name` and `k8s.namespace.name`.** Rejected: the span resource of devops-cli does not read this variable (`OTelTelemetryClient`), only the metric resource does. #2536 owns the move to the SDK resource.
- **`k8s.context` in the ConfigMap.** Rejected: the setting also names the kubeconfig context of the commands (`src/devops_cli/k8s/api.py`), so a telemetry label would change what the commands connect to. The live ConfigMap is also outside Argo CD, and this item does not change it.
- **A ConfigMap that holds the cluster name.** Rejected: a generated name with a hash needs a name reference in the WorkflowTemplate, which Kustomize does not change, and one literal value per container is simpler. The check holds the 5 values equal.
- **Remove the `minikube` default of `k8s.context`.** Rejected for this item: the default is the target of the workstation commands, not only a telemetry label.
