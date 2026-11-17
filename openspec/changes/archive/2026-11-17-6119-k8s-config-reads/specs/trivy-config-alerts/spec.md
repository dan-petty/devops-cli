## MODIFIED Requirements

### Requirement: The GPU feature discovery workload sets a read-only root file system
The `k8s/gpu-feature-discovery/daemonset.yaml` manifest SHALL configure `readOnlyRootFilesystem: true` in the container `securityContext` of `gpu-feature-discovery`.

#### Scenario: The manifest sets a read-only root file system
- **WHEN** `uv run devops k8s lint k8s/gpu-feature-discovery` runs kube-linter on the manifests
- **THEN** kube-linter reports no writable root file system for `gpu-feature-discovery`, and `devops scan` reports no `trivy config` finding KSV-0014 for it
