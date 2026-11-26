## ADDED Requirements

### Requirement: A lint needs a Kubernetes object and reads the config of its repository
`devops k8s lint` SHALL run kube-linter with `--fail-if-no-objects-found`, so that a TARGET or a build with no Kubernetes object fails. With a TARGET, it SHALL give `--config` at the `.kube-linter.yaml` of the repository that holds the TARGET when that file exists.

#### Scenario: A folder with no object
- **WHEN** `devops k8s lint <repository>/k8s/devops` runs and kube-linter reports that it found no object
- **THEN** the command exits 1, and kube-linter got `--fail-if-no-objects-found`

#### Scenario: The config of the repository of the target
- **WHEN** the repository of the TARGET holds `.kube-linter.yaml`
- **THEN** kube-linter gets `--config` at that file
