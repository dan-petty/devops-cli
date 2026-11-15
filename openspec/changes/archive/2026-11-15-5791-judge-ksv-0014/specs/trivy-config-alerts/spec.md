## ADDED Requirements

### Requirement: The GPU feature discovery workload sets a read-only root file system
The `k8s/gpu-feature-discovery/daemonset.yaml` manifest SHALL configure `readOnlyRootFilesystem: true` in the container `securityContext` of `gpu-feature-discovery`.

#### Scenario: The manifest sets a read-only root file system
- **WHEN** a test loads `k8s/gpu-feature-discovery/daemonset.yaml` and inspects the `gpu-feature-discovery` container
- **THEN** it finds `readOnlyRootFilesystem` set to `true`, `privileged` set to `true`, and both `output-dir` and `host-sys` volumes configured
