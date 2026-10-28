## Purpose

The `devops k8s validate` command validates Kubernetes manifests against their JSON schemas with the kubeconform that `tools.lock` pins, and never reports a pass when kubeconform did not run.

## ADDED Requirements

### Requirement: A validation that did not run is no pass
The `devops k8s validate` command SHALL exit 1 and say that the validation did not run, with the status and the reason of the scan, when kubeconform did not run. It SHALL NOT say that the manifests are valid.

#### Scenario: kubeconform is not on the path
- **WHEN** `devops k8s validate <manifest>` runs and no directory of PATH holds kubeconform
- **THEN** the command says that the kubeconform validation is `unavailable` because `Binary 'kubeconform' not found on PATH`, says no pass, and exits 1

### Requirement: A clean validation passes
The `devops k8s validate` command SHALL say that the manifests are valid and exit 0 only when kubeconform ran and reported no invalid resource.

#### Scenario: kubeconform finds nothing
- **WHEN** `devops k8s validate <manifest>` runs, and kubeconform writes `{"resources": []}` and exits 0
- **THEN** the command says that the manifests are valid and exits 0
