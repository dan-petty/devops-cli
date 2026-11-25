## ADDED Requirements

### Requirement: Each sandbox NetworkPolicy has one policy type
`SandboxNetworkConfig.to_k8s_network_policy` SHALL return a tuple of two `NetworkPolicy` objects for every network mode: an Ingress-only policy (`policyTypes: ["Ingress"]`) first and an Egress-only policy (`policyTypes: ["Egress"]`) second, with distinct trimmed DNS subdomain names (`-ingress` and `-egress`), shared `podSelector`, and direction-only rules. `devops sandbox network-policy` SHALL emit both objects as multi-document YAML.

#### Scenario: Every network mode yields a single-type pair
- **WHEN** `SandboxNetworkConfig.to_k8s_network_policy` runs for each `SandboxNetworkMode`
- **THEN** it returns two `NetworkPolicy` objects whose `policyTypes` are `["Ingress"]` and `["Egress"]`, neither holds both types, their `metadata.name` values differ and match DNS subdomain rules, and the union of their directional rules equals the rules of that mode

#### Scenario: Isolated mode denies both directions
- **WHEN** `SandboxNetworkConfig.to_k8s_network_policy` runs for `isolated` mode
- **THEN** it returns an Ingress-only policy with `ingress: []` and an Egress-only policy with `egress: []`, and `devops sandbox network-policy` emits both YAML documents
