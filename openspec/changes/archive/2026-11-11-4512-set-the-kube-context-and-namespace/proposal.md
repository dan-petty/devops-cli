# Proposal: #4512

## Why

Issue #4512: the spans and the OTLP log records of the devops-cli pods name the wrong cluster. All 1,705 `roadmap-service` spans of 2026-11-11 03:50Z-04:04Z have `k8s.cluster.name=minikube`, and the runner log records have `k8s_cluster_name=minikube`. The workstation spans have `homelab-k3s`, the cluster name of the monitoring stack. The pod spans also have no `k8s.namespace.name`.

`_detect_k8s_context` in `src/devops_cli/telemetry/tracer.py` reads `K8S_CONTEXT` and `POD_NAMESPACE` from the environment first. No pod spec in `k8s/devops/` sets them, so the tracer uses the setting `k8s.context`, whose default is `minikube`.

## What Changes

- Each devops-cli container in `k8s/devops/` sets `K8S_CONTEXT` to `homelab-k3s`, the cluster name in `k8s/monitoring/k8s-monitoring-values.yaml`, and `POD_NAMESPACE` to the namespace of its pod. The containers are those of Deployment `roadmap-service`, Deployment `mcp-server`, CronJob `devops-cli`, CronJob `devops-cli-runner` (the runner Job template) and WorkflowTemplate `rag-ingest`: 5 containers, counted from the render of `kubectl kustomize k8s/devops`.
- `POD_NAMESPACE` comes from the Downward API (`metadata.namespace`). The runner template is the exception: the admission policy `roadmap-service-jobs` refuses an env entry with `valueFrom` in a Job of the Service, so the template sets the plain value `devops`.
- A new check of the `k8s` row of `devops ci`, `tests/gate/k8s_checks/telemetry_resource.py`, fails when one of the 5 containers does not set both values, or when the render has another devops-cli container.
- A new test in `tests/telemetry/test_telemetry.py` holds the names of the two environment values that the tracer reads.
- `k8s/README.md` (section devops-cli in the cluster) describes the two values.
- The manifests change what the pods send, so the change has a spec delta.
- Not changed: the code of the tracer, the setting `k8s.context`, `service.instance.id` and `k8s.pod.name`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-telemetry`: a new requirement, "A devops-cli pod names its cluster and its namespace".

## Impact

- `k8s/devops/roadmap-service/deployment.yaml`, `k8s/devops/mcp-server/deployment.yaml`, `k8s/devops/cronjob.yaml`, `k8s/devops/cronjob-runner.yaml`, `k8s/devops/workflowtemplate-rag-ingest.yaml`, `k8s/README.md`.
- `tests/gate/k8s_checks/telemetry_resource.py`, `tests/telemetry/test_telemetry.py`.
- Argo CD applies the manifests after the merge. The live ConfigMap and the Secrets need no change. The change fits one pull request.

## Feasibility

Read on 2026-11-11.

- `src/devops_cli/telemetry/tracer.py`, `_detect_k8s_context`: `ctx = os.getenv("K8S_CONTEXT") or os.getenv("KUBECONFIG_CONTEXT")` and `ns = os.getenv("K8S_NAMESPACE") or os.getenv("POD_NAMESPACE")`. Only when `K8S_CONTEXT` is not set does it read `k8s.context` from the settings. The span resource takes `k8s.cluster.name` from this function, and each span takes `k8s.namespace.name`. The OTLP log records use the same resource. No other code in `src/` reads these two names (`git grep`), so the values change only the telemetry.
- The study of 2026-11-11 measured the wrong name with TraceQL `{ } | count_over_time() by (resource.service.name, resource.k8s.cluster.name)`.
- `k8s/devops/roadmap-service/admissionpolicy.yaml` holds the rule `c.env.all(e, !has(e.valueFrom))` for a Job of the Service. The check `tests/gate/k8s_checks/job_admission_policy.py` runs the policy against a Job that `build_job` makes from the runner template. With the plain value it passes (`uv run devops ci --only k8s`: 104 cases, 0 failed).
- The name `homelab-k3s` is already in `k8s/monitoring/k8s-monitoring-values.yaml`, `k8s/monitoring/prometheus-values.yaml` and `k8s/otel/values.yaml`. It is a cluster name, not a host name.
- Kubernetes documents `fieldRef` with `metadata.namespace` for container environment values (https://kubernetes.io/docs/tasks/inject-data-application/environment-variable-expose-pod-information/). Argo Workflows takes a Kubernetes container spec in a template, so the WorkflowTemplate takes the same entry.

## Existing Tool Considered

The Kubernetes Downward API gives the namespace, and no code is built. The standard `OTEL_RESOURCE_ATTRIBUTES` is not used, because the span resource of devops-cli does not read it (only the metric resource does); #2536 moves the spans to the OpenTelemetry SDK. The change deletes no internal code.
