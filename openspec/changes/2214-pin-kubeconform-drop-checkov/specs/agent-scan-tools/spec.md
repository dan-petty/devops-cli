## ADDED Requirements

### Requirement: The manifest validation and IaC tools run the pinned adapters
The agent tool `k8s_validate_manifests` SHALL run the kubeconform adapter over its target, a path inside the workspace. The agent tool `scan_iac` SHALL run the Trivy adapter with the scan type `config` over its target. Each SHALL keep no command line of its own, and SHALL reply as the other agent scan tools reply.

#### Scenario: kubeconform is not installed
- **WHEN** no directory of PATH holds kubeconform, and the agent calls `k8s_validate_manifests` over a manifest
- **THEN** the reply is `Kubeconform scan status: not installed`, then `Reason: Binary 'kubeconform' not found on PATH`, then `The scan gave no result. Do not report the target as clean.`

#### Scenario: kubeconform finds invalid resources
- **WHEN** the agent calls `k8s_validate_manifests` over a manifest directory in which kubeconform reports three resources
- **THEN** the reply is `Kubeconform scan status: ok`, then `Findings (3):`, then one line for each finding

#### Scenario: The IaC tool runs Trivy's misconfiguration scan
- **WHEN** the agent calls `scan_iac` over a directory
- **THEN** Trivy starts with `config` over that directory, and the reply starts with `Trivy scan status:`
