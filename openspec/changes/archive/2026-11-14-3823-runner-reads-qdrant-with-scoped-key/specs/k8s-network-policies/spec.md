## ADDED Requirements

### Requirement: Egress to Qdrant on TCP 6333
The devops perimeter SHALL admit egress from the pods of namespace `devops` to namespace `llm` on TCP 6333 only.

#### Scenario: The policy admits the Qdrant port
- **WHEN** a test reads `k8s/devops/networkpolicy.yaml`
- **THEN** it finds one egress rule whose peer is the namespace selector of `llm` and whose only port is TCP 6333

### Requirement: Qdrant admits the devops namespace
The policy that selects the Qdrant pod SHALL admit ingress from namespace `devops` on TCP 6333.

#### Scenario: The Qdrant pod admits the runner
- **WHEN** a test reads `k8s/llm/networkpolicy.yaml`
- **THEN** it finds an ingress rule whose peer is the namespace selector of `devops` and whose port is TCP 6333

### Requirement: The README names the Qdrant route
`k8s/README.md` SHALL name the Qdrant route of the devops namespace on TCP 6333.

#### Scenario: The README lists the route
- **WHEN** a test reads the section of `k8s/README.md` on devops-cli in the cluster
- **THEN** it names Qdrant on TCP 6333 beside the gateway, the cache and the collector
