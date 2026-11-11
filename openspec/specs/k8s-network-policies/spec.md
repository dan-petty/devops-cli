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

### Requirement: The cert-manager perimeter admits only the metrics scrape and the API server
The NetworkPolicy `cert-manager-default-perimeter` SHALL admit ingress to every pod of namespace `cert-manager` only from namespace `monitoring` on TCP 9402, and SHALL allow egress only to CoreDNS and to the API server on TCP 443 and 6443 through an ipBlock that excludes 169.254.169.254/32. The NetworkPolicy `cert-manager-webhook` SHALL select only the webhook pods and admit only TCP 10250.

#### Scenario: The cert-manager perimeter peers
- **WHEN** a test reads `cert-manager-default-perimeter` in `k8s/cert-manager/networkpolicy.yaml`
- **THEN** its one ingress rule admits namespace `monitoring` on TCP 9402, and its egress rules are CoreDNS on port 53 and the ipBlock on TCP 443 and 6443

#### Scenario: The webhook policy opens one port on the webhook pods
- **WHEN** a test reads `cert-manager-webhook` in `k8s/cert-manager/networkpolicy-webhook.yaml`
- **THEN** it selects the pods with `app.kubernetes.io/name: webhook` and `app.kubernetes.io/component: webhook`, and its one ingress rule admits TCP 10250

### Requirement: Only the CloudNativePG operator reaches the Barman Cloud plugin
The NetworkPolicy `plugin-barman-cloud` in namespace `cnpg-system` SHALL select only the pods with `app.kubernetes.io/name: plugin-barman-cloud`, SHALL admit ingress only from the pods with `app.kubernetes.io/name: cloudnative-pg` on TCP 9090, and SHALL allow egress only to CoreDNS and to the API server on TCP 443 and 6443.

#### Scenario: The plugin policy peers
- **WHEN** a test reads `plugin-barman-cloud` in `k8s/cnpg-system/networkpolicy.yaml`
- **THEN** its one ingress rule admits the operator pods on TCP 9090, and its egress rules are CoreDNS on port 53 and the API server ipBlock on TCP 443 and 6443
