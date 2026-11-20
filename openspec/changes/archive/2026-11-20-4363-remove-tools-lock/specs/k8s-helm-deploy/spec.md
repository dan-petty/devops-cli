## MODIFIED Requirements

### Requirement: Kubectl version skew notification
Before deploying stack resources or applying Helm releases, the deployment process SHALL check whether the version of the `kubectl` on PATH, from `kubectl version --client -o json`, is outside the supported minor version skew of the Kubernetes API server. If a skew is detected, the deployment SHALL print a warning message naming both versions and the supported range, and continue deployment.

#### Scenario: Skew detected before deployment
- **WHEN** `devops k8s deploy-stack` runs against a cluster whose API server minor differs from the minor of the `kubectl` on PATH by more than one
- **THEN** a warning message naming both versions and the supported range is emitted and the deployment continues

#### Scenario: No skew detected
- **WHEN** `devops k8s deploy-stack` runs against a cluster whose API server is within one minor version of the `kubectl` on PATH
- **THEN** no version skew warning is printed
