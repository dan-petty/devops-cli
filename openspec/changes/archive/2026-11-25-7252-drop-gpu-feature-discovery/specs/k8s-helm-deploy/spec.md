## ADDED Requirements

### Requirement: A native deploy applies no GPU feature discovery
`devops k8s deploy-stack` of the stacks `infra` and `all` SHALL apply the kustomization `monitoring` of the environment tree and SHALL NOT apply a kustomization `gpu-feature-discovery`.

#### Scenario: Dry run of the infra stack
- **WHEN** a person runs `devops k8s deploy-stack --stack infra --k8s-dir <tree> --dry-run`
- **THEN** the listed kustomizations after the root one are `<tree>/monitoring` only
