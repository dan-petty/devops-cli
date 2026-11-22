## ADDED Requirements

### Requirement: A policy with both types gives its own pods no path past its ingress rules
The `k8s` row SHALL refuse each NetworkPolicy of `k8s/` with the types `Ingress` and `Egress` whose egress rule reaches a pod that the policy selects on a port that no ingress rule of the policy admits from all its pods. A rule with no `to`, a pod peer of the own namespace and an `ipBlock` with a private range reach such a pod. The problem SHALL name the policy, the rule, the port and kube-router, which applies no ingress rule to that traffic.

#### Scenario: An in-namespace egress rule with no ports
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on a fixture policy with both types, the pod selector `{}`, an ingress rule from `podSelector: {}` on TCP 3000 and an egress rule to `podSelector: {}` with no `ports`
- **THEN** the rule reports a problem that names the fixture policy and kube-router

#### Scenario: An ingress rule that limits the peer
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on a fixture policy with both types whose ingress rule admits only some of its pods, and whose egress rule to the own pods names TCP 3000
- **THEN** the rule reports a problem that names the fixture policy and TCP 3000

#### Scenario: An ipBlock and a rule with no peer
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on a fixture policy with both types, an egress rule to `ipBlock: 0.0.0.0/0` on TCP 443 and an egress rule with no `to` on UDP 53
- **THEN** the rule reports one problem for each of the two rules, and no problem for an `ipBlock` that excepts the private ranges

#### Scenario: Single-type and aligned policies
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on an ingress-only policy, an egress-only policy with an in-namespace egress rule with no ports, a policy with both types whose in-namespace egress rule names the port that its ingress rule admits from `podSelector: {}`, a policy with both types whose egress peer is in another namespace, and a policy with both types whose egress peer selects other pods
- **THEN** the rule reports no problem

#### Scenario: The environment tree
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on each NetworkPolicy of `k8s/`
- **THEN** the rule reports no problem

#### Scenario: The live cluster
- **WHEN** a person runs `kubectl get networkpolicy -A -o json` after Argo CD syncs `main`, and selects each policy with both types
- **THEN** only the 4 policies of namespace `devops` have both types, and in each namespace with split policies a probe pod that the ingress rules do not admit cannot connect to a limited port, on the node of the server pod and on a second node

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
