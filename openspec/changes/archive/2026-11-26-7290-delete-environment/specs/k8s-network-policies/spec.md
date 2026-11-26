## ADDED Requirements

### Requirement: Each product NetworkPolicy has both apply paths
The `k8s` row SHALL refuse a NetworkPolicy of `k8s/devops/` that the build of the root kustomization does not hold, or that no product table of `deploy-stack` applies.

#### Scenario: The root kustomization drops a policy
- **WHEN** `uv run devops ci --check --only k8s` runs on a tree whose `k8s/devops/kustomization.yaml` does not list a file of a NetworkPolicy
- **THEN** it exits non-zero

### Requirement: No product NetworkPolicy has both types
The `k8s` row SHALL refuse each NetworkPolicy of `k8s/devops/` whose types hold `Ingress` and `Egress`. The row SHALL read the types as the API server sets them: `policyTypes` as written; with no `policyTypes`, `Ingress`, and `Egress` when the policy has an egress rule. The problem SHALL name the policy and kube-router, which lets the rules of one type of such a policy skip the rules of the other type for traffic between two pods that the policy selects.

#### Scenario: A policy that writes both types
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on a fixture policy with `policyTypes: [Ingress, Egress]`
- **THEN** the rule reports a problem that names the fixture policy and kube-router

#### Scenario: A policy with no types and an egress rule
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on a fixture policy with no `policyTypes` and an egress rule
- **THEN** the rule reports a problem that names the fixture policy

#### Scenario: Single-type policies
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on a policy with `policyTypes: [Ingress]`, a policy with `policyTypes: [Egress]`, a policy with no `policyTypes` and no egress section, and a policy with no `policyTypes` and an empty egress list
- **THEN** the rule reports no problem

#### Scenario: The product base
- **WHEN** `uv run devops ci --check --only k8s` runs the rule on each NetworkPolicy of `k8s/devops/`
- **THEN** the rule reports no problem

## REMOVED Requirements

### Requirement: Network policy namespace selectors reference declared or built-in namespaces
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Portkey perimeter admits traffic from stack workloads and monitoring only
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: OpenTelemetry perimeter ingress admits monitoring and Traefik in kube-system
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: No Ingress targets the logging namespace
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The cert-manager perimeter admits only the metrics scrape and the API server
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Only the CloudNativePG operator reaches the Barman Cloud plugin
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: Qdrant admits the devops namespace
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: The monitoring perimeter admits the SearXNG metrics scrape
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: No NetworkPolicy has both types
**Reason**: The row reads the product base only (#7290).
**Migration**: See `No product NetworkPolicy has both types`.
