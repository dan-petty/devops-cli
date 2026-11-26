# k8s-lint Specification

## Purpose
The `devops k8s lint` command audits a manifest or Helm chart with Kube-linter, reports what it found, and sets its exit code as the gate: a pass only when Kube-linter ran and found nothing.

## Requirements

### Requirement: A clean audit passes
The `devops k8s lint` command SHALL exit 0 and report a pass only when Kube-linter ran and reported no finding.

#### Scenario: Kube-linter runs and finds nothing
- **WHEN** `devops k8s lint <manifest>` runs and Kube-linter reports no finding
- **THEN** the command reports the audit passed and exits 0

### Requirement: Findings fail the audit
The `devops k8s lint` command SHALL exit non-zero and report the findings when Kube-linter ran and reported at least one finding.

#### Scenario: Kube-linter flags a misconfiguration
- **WHEN** `devops k8s lint <manifest>` runs and Kube-linter reports one or more findings
- **THEN** the command reports the findings, reports no pass, and exits non-zero

### Requirement: A scan that did not run fails the audit
The `devops k8s lint` command SHALL exit non-zero and say the scan did not run when Kube-linter did not run, and SHALL report no pass.

#### Scenario: Kube-linter is not on the path
- **WHEN** `devops k8s lint <manifest>` runs and Kube-linter is unavailable
- **THEN** the command says the scan did not run, reports no pass, and exits non-zero

### Requirement: The lint of the environment tree reads the build of each path source
With no TARGET, `devops k8s lint` SHALL build each path source of the Argo CD Applications of the environment tree with Kustomize into a file of its own, `<application>-<index>.yaml`, in one folder that holds no other file. A source of the repository that holds the tree SHALL come from the checkout, and a source of another public repository SHALL be fetched at its revision. A chart source SHALL NOT be built.

#### Scenario: A chart source and a source of another repository
- **WHEN** an Application has a chart source, a path source of the repository and a path source of another repository
- **THEN** the folder holds the builds of the two path sources, named for the Application and the place of each source, no `helm template` runs, and the fetched repository is outside the folder

### Requirement: The lint of the environment tree uses the config of the repository
With no TARGET, `devops k8s lint` SHALL lint the folder of the builds in one kube-linter run, with `--config` at the `.kube-linter.yaml` of the repository that holds the tree when that file exists. The command SHALL exit 1 on a finding, and when kube-linter did not run.

#### Scenario: The builds are linted with the config of the repository
- **WHEN** `devops k8s lint --k8s-dir <tree>` runs on a tree whose Application has one path source, and the repository holds `.kube-linter.yaml`
- **THEN** kube-linter reads one folder that holds only the build of that source, gets `--config` at that file, and a finding makes the command exit 1

#### Scenario: A repository with no config
- **WHEN** the repository that holds the tree has no `.kube-linter.yaml`
- **THEN** kube-linter gets no `--config` and runs its default checks

### Requirement: A lint needs a Kubernetes object and reads the config of its repository
`devops k8s lint` SHALL run kube-linter with `--fail-if-no-objects-found`, so that a TARGET or a build with no Kubernetes object fails. With a TARGET, it SHALL give `--config` at the `.kube-linter.yaml` of the repository that holds the TARGET when that file exists.

#### Scenario: A folder with no object
- **WHEN** `devops k8s lint <repository>/k8s/devops` runs and kube-linter reports that it found no object
- **THEN** the command exits 1, and kube-linter got `--fail-if-no-objects-found`

#### Scenario: The config of the repository of the target
- **WHEN** the repository of the TARGET holds `.kube-linter.yaml`
- **THEN** kube-linter gets `--config` at that file
