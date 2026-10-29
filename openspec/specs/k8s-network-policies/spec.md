# k8s-network-policies Specification

## Purpose
Provides namespace selector validation and isolation invariants for Kubernetes NetworkPolicies.

## Requirements

### Requirement: Network policy namespace selectors reference declared or built-in namespaces
Every `kubernetes.io/metadata.name` label selector declared under `namespaceSelector` in Kubernetes NetworkPolicies SHALL reference a namespace declared in `k8s/namespaces.yaml` or a standard built-in namespace (`kube-system`, `default`).

#### Scenario: Valid namespace selectors
- **WHEN** the test suite audits all `namespaceSelector` blocks in Kubernetes NetworkPolicies
- **THEN** every referenced namespace exists in `k8s/namespaces.yaml` or matches `kube-system` or `default`

#### Scenario: Unmatched namespace selector detected
- **WHEN** a NetworkPolicy includes a `namespaceSelector` matching an undeclared namespace
- **THEN** the manifest validation check fails and identifies the offending file and namespace

### Requirement: Portkey perimeter admits traffic from stack workloads and monitoring only
The Portkey perimeter NetworkPolicy (`k8s/llm/portkey/networkpolicy.yaml`) SHALL restrict ingress traffic on port 8787 to pods labeled `app.kubernetes.io/part-of: devops-cli-stack` and the `monitoring` namespace.

#### Scenario: Portkey perimeter ingress peers
- **WHEN** inspecting the ingress configuration of `portkey-perimeter`
- **THEN** ingress admits only `devops-cli-stack` pods and namespace `monitoring` on TCP port 8787

### Requirement: OpenTelemetry perimeter ingress admits monitoring and Traefik in kube-system
The OpenTelemetry default perimeter NetworkPolicy (`k8s/otel/networkpolicy.yaml`) SHALL admit ingress to port 3200 from the `monitoring` namespace and from Traefik pods in the `kube-system` namespace.

#### Scenario: OpenTelemetry perimeter ingress peers
- **WHEN** inspecting the ingress rule for port 3200 of `otel-default-perimeter`
- **THEN** ingress admits only namespace `monitoring` and Traefik pods in namespace `kube-system`

### Requirement: No Ingress targets the logging namespace
No Ingress in the cluster SHALL route to a Service in namespace `logging`. `k8s/ingress/ingress-routes.yaml` SHALL NOT hold an Ingress named `loki-ingress`, and no Ingress document under `k8s/` SHALL set `metadata.namespace` to `logging`.

#### Scenario: The route list holds no loki-ingress
- **WHEN** a test reads the Ingress names in `k8s/ingress/ingress-routes.yaml`
- **THEN** no Ingress is named `loki-ingress`

#### Scenario: No Ingress document is in the logging namespace
- **WHEN** a test reads the Ingresses under `k8s/`
- **THEN** no Ingress sets `metadata.namespace` to `logging`
