## ADDED Requirements

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

## MODIFIED Requirements

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

### Requirement: The planner run Job denies all egress
The stack SHALL hold a NetworkPolicy that selects the pod label `app.kubernetes.io/name: devops-cli-planner-run`, sets `policyTypes: [Egress]` and holds no egress rule. The default perimeter NetworkPolicies `devops-default-perimeter-ingress` and `devops-default-perimeter-egress` SHALL exclude `devops-cli-planner-run` from their pod selectors so that the planner run pod reaches no network.

#### Scenario: The egress rules of the planner run Job pod
- **WHEN** `uv run devops ci --check --only k8s` renders `k8s/devops`
- **THEN** the row passes only when the planner policy is the one NetworkPolicy that selects the pod of CronJob `devops-cli-planner-run`, and that policy holds `Egress` and no egress rule

#### Scenario: A pod with the planner label reaches no address
- **WHEN** a throwaway pod with the label `app.kubernetes.io/name: devops-cli-planner-run` in namespace `devops` runs `nc -w 3 <CoreDNS Service address> 53`, started with `kubectl run --rm -i --restart=Never`
- **THEN** the connect times out, so the pod reaches not even DNS
