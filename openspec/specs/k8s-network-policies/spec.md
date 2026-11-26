# k8s-network-policies Specification

## Purpose
The isolation invariants of the NetworkPolicies of the product base `k8s/devops`.

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
The Portkey ingress policy (`k8s/llm/portkey/networkpolicy.yaml`) SHALL restrict ingress traffic on port 8787 to pods labeled `app.kubernetes.io/part-of: devops-cli-stack` and the `monitoring` namespace.

#### Scenario: Portkey perimeter ingress peers
- **WHEN** inspecting the ingress configuration of `portkey-perimeter-ingress`
- **THEN** ingress admits only `devops-cli-stack` pods and namespace `monitoring` on TCP port 8787

### Requirement: OpenTelemetry perimeter ingress admits monitoring and Traefik in kube-system
The OpenTelemetry default ingress policy (`k8s/otel/networkpolicy.yaml`) SHALL admit ingress to port 3200 from the `monitoring` namespace and from Traefik pods in the `kube-system` namespace.

#### Scenario: OpenTelemetry perimeter ingress peers
- **WHEN** inspecting the ingress rule for port 3200 of `otel-default-perimeter-ingress`
- **THEN** ingress admits only namespace `monitoring` and Traefik pods in namespace `kube-system`

### Requirement: No Ingress targets the logging namespace
No Ingress in the cluster SHALL route to a Service in namespace `logging`. `k8s/ingress/ingress-routes.yaml` SHALL NOT hold an Ingress named `loki-ingress`, and no Ingress document under `k8s/` SHALL set `metadata.namespace` to `logging`.

#### Scenario: The route list holds no loki-ingress
- **WHEN** a person runs `kubectl get ingress --all-namespaces` after Argo CD syncs the tree
- **THEN** no Ingress is named `loki-ingress`

#### Scenario: No Ingress document is in the logging namespace
- **WHEN** a person runs `kubectl -n logging get ingress` after Argo CD syncs the tree
- **THEN** the namespace holds no Ingress

### Requirement: The cert-manager perimeter admits only the metrics scrape and the API server
The NetworkPolicy `cert-manager-default-perimeter-ingress` SHALL admit ingress to every pod of namespace `cert-manager` only from namespace `monitoring` on TCP 9402, and the NetworkPolicy `cert-manager-default-perimeter-egress` SHALL allow egress only to CoreDNS and to the API server on TCP 443 and 6443 through an ipBlock that excludes 169.254.169.254/32. The NetworkPolicy `cert-manager-webhook` SHALL select only the webhook pods and admit only TCP 10250.

#### Scenario: The cert-manager perimeter peers
- **WHEN** a throwaway pod in namespace `monitoring` and a throwaway pod in namespace `default` each run `nc -w 3 <cert-manager pod address> 9402`, and a throwaway pod in namespace `cert-manager` runs `nc -w 3 kubernetes.default.svc 443` and `nc -w 3 169.254.169.254 80`, each started with `kubectl run --rm -i --restart=Never`
- **THEN** the connect from `monitoring` succeeds and the connect from `default` times out
- **AND** the connect to the API server succeeds and the connect to the metadata address times out

#### Scenario: The webhook policy opens one port on the webhook pods
- **WHEN** a person applies a cert-manager `Certificate` with `kubectl apply --dry-run=server`
- **THEN** the API server calls the webhook on TCP 10250, and the webhook admits or refuses the object with no timeout

### Requirement: Only the CloudNativePG operator reaches the Barman Cloud plugin
The NetworkPolicies `plugin-barman-cloud-ingress` and `plugin-barman-cloud-egress` in namespace `cnpg-system` SHALL select only the pods with `app.kubernetes.io/name: plugin-barman-cloud`. The ingress policy SHALL admit ingress only from the pods with `app.kubernetes.io/name: cloudnative-pg` on TCP 9090, and the egress policy SHALL allow egress only to CoreDNS and to the API server on TCP 443 and 6443.

#### Scenario: The plugin policy peers
- **WHEN** a throwaway pod with the label `app.kubernetes.io/name: cloudnative-pg` and a throwaway pod with no label, both in namespace `cnpg-system`, each run `nc -w 3 <plugin pod address> 9090`, started with `kubectl run --rm -i --restart=Never`
- **THEN** the connect of the pod with the operator label succeeds, and the connect of the other pod times out

### Requirement: Egress to Qdrant on TCP 6333
The devops perimeter SHALL admit egress from the pods of namespace `devops` to namespace `llm` on TCP 6333 only.

#### Scenario: The policy admits the Qdrant port
- **WHEN** a throwaway pod in namespace `devops` runs `nc -w 3 qdrant.llm.svc.cluster.local 6333` and `nc -w 3 qdrant.llm.svc.cluster.local 6334`, started with `kubectl run --rm -i --restart=Never`
- **THEN** the connect to TCP 6333 succeeds, and the connect to TCP 6334 times out

### Requirement: Qdrant admits the devops namespace
The policy that selects the Qdrant pod SHALL admit ingress from namespace `devops` on TCP 6333.

#### Scenario: The Qdrant pod admits the runner
- **WHEN** a throwaway pod in namespace `devops` and a throwaway pod in namespace `default` each run `nc -w 3 qdrant.llm.svc.cluster.local 6333`, started with `kubectl run --rm -i --restart=Never`
- **THEN** the connect from `devops` succeeds, and the connect from `default` times out

### Requirement: The planner run Job denies all egress
The stack SHALL hold a NetworkPolicy that selects the pod label `app.kubernetes.io/name: devops-cli-planner-run`, sets `policyTypes: [Egress]` and holds no egress rule. The default perimeter NetworkPolicies `devops-default-perimeter-ingress` and `devops-default-perimeter-egress` SHALL exclude `devops-cli-planner-run` from their pod selectors so that the planner run pod reaches no network.

#### Scenario: The egress rules of the planner run Job pod
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/devops`
- **THEN** the row passes only when the planner policy is the one NetworkPolicy that selects the pod of CronJob `devops-cli-planner-run`, and that policy holds `Egress` and no egress rule

#### Scenario: A pod with the planner label reaches no address
- **WHEN** a throwaway pod with the label `app.kubernetes.io/name: devops-cli-planner-run` in namespace `devops` runs `nc -w 3 <CoreDNS Service address> 53`, started with `kubectl run --rm -i --restart=Never`
- **THEN** the connect times out, so the pod reaches not even DNS

### Requirement: No NetworkPolicy has both types
The `k8s` row SHALL refuse each NetworkPolicy of `k8s/` whose types hold `Ingress` and `Egress`. The row SHALL read the types as the API server sets them: `policyTypes` as written; with no `policyTypes`, `Ingress`, and `Egress` when the policy has an egress rule. The problem SHALL name the policy and kube-router, which lets the rules of one type of such a policy skip the rules of the other type for traffic between two pods that the policy selects.

#### Scenario: A policy that writes both types
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on a fixture policy with `policyTypes: [Ingress, Egress]`
- **THEN** the rule reports a problem that names the fixture policy and kube-router

#### Scenario: A policy with no types and an egress rule
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on a fixture policy with no `policyTypes` and an egress rule
- **THEN** the rule reports a problem that names the fixture policy

#### Scenario: Single-type policies
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on a policy with `policyTypes: [Ingress]`, a policy with `policyTypes: [Egress]`, a policy with no `policyTypes` and no egress section, and a policy with no `policyTypes` and an empty egress list
- **THEN** the rule reports no problem

#### Scenario: The environment tree
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on each NetworkPolicy of `k8s/`
- **THEN** the rule reports no problem

#### Scenario: The live cluster
- **WHEN** a person runs `kubectl get networkpolicy -A -o json` after Argo CD syncs `main`, and selects each policy whose `policyTypes` hold `Ingress` and `Egress`
- **THEN** no policy is selected, and in each namespace with split policies a probe pod that the ingress rules do not admit cannot connect to a limited port, on the node of the server pod and on a second node

### Requirement: The monitoring perimeter admits the SearXNG metrics scrape
The `monitoring-default-perimeter-egress` NetworkPolicy SHALL admit namespace `devops` to TCP port 8080 beside port 8000, so that a scrape of the SearXNG pod leaves the monitoring namespace.

#### Scenario: The k8s check accepts the new egress port
- **WHEN** `uv run devops ci --check --only k8s` runs on the branch that changes `k8s/monitoring/networkpolicy.yaml`
- **THEN** the check exits 0 and reports no error for `k8s/monitoring/networkpolicy.yaml`
