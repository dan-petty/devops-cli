## Purpose

The `devops k8s validate` command validates Kubernetes manifests against their JSON schemas with the kubeconform that `tools.lock` pins. It never reports a pass when kubeconform did not run.

## ADDED Requirements

### Requirement: A validation that did not run is no pass
When kubeconform did not run, the `devops k8s validate` command SHALL exit 1 and say that the validation did not run. It SHALL give the status and the reason of the scan. It SHALL NOT say that the manifests are valid.

#### Scenario: kubeconform is not on the path
- **WHEN** `devops k8s validate <manifest>` runs and no directory of PATH holds kubeconform
- **THEN** the command says that the kubeconform validation is `unavailable` because `Binary 'kubeconform' not found on PATH`, says no pass, and exits 1

#### Scenario: The target holds no manifest
- **WHEN** `devops k8s validate <directory>` runs over a directory that holds no Kubernetes manifest
- **THEN** the command says that the kubeconform validation is `not_applicable` because `No Kubernetes manifest in the target`, says no pass, and exits 1

### Requirement: A clean validation passes
The `devops k8s validate` command SHALL say that the manifests are valid only when kubeconform ran and reported no invalid resource, and SHALL then exit 0.

#### Scenario: kubeconform finds nothing
- **WHEN** `devops k8s validate <manifest>` runs, and kubeconform writes `{"resources": []}` and exits 0
- **THEN** the command says that the manifests are valid and exits 0
