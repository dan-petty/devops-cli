## ADDED Requirements

### Requirement: kubeconform reads the one report object that it writes
The kubeconform adapter SHALL run the kubeconform that `tools.lock` pins with `-output json`. The parser SHALL give one HIGH finding for each resource of the report with the status `statusInvalid` or `statusError`, at `<manifest>:<Kind>/<name>`, and no finding for `statusValid` or `statusSkipped`.

#### Scenario: kubeconform finds two invalid resources and one it cannot validate
- **WHEN** kubeconform 0.8.0 validates a manifest directory, exits 1, and reports the ConfigMap `settings` and the Service `web` as `statusInvalid` and the Widget `blue` as `statusError`
- **THEN** the scan ran, and its findings are three HIGH findings, at `k8s/app.yaml:Widget/blue`, `k8s/app.yaml:ConfigMap/settings` and `k8s/app.yaml:Service/web`, in the order of the report

#### Scenario: A verbose report also lists valid and skipped resources
- **WHEN** the parser reads a kubeconform 0.8.0 `-verbose` report with one resource of each status
- **THEN** the findings are two HIGH findings, for the `statusError` resource and the `statusInvalid` resource

#### Scenario: kubeconform finds nothing
- **WHEN** kubeconform writes `{"resources": []}` and exits 0
- **THEN** the scan ran and has no finding

### Requirement: kubeconform validates only the manifests of the target
The kubeconform adapter SHALL give kubeconform the path of each Kubernetes manifest of the target that git lists and does not ignore, and SHALL give it no other file. When the target holds no manifest, the scan SHALL be `not_applicable`, and kubeconform SHALL NOT start.

#### Scenario: A directory holds manifests and other YAML and JSON files
- **WHEN** the adapter validates a directory that holds a manifest, a Helm values file, a Helm template, a dashboard, a workflow, a package file, and a manifest in a directory that git ignores
- **THEN** kubeconform starts once, and its command names only the manifest

#### Scenario: A directory holds no manifest
- **WHEN** the adapter validates a directory that holds no manifest
- **THEN** the outcome status is `not_applicable`, the reason is `No Kubernetes manifest in the target`, and kubeconform does not start

### Requirement: A pinned tool has no hand-written fallback
The kubeconform adapter SHALL keep no built-in patterns. When no directory of PATH holds kubeconform, the scan SHALL be `unavailable` with the reason `Binary 'kubeconform' not found on PATH`, and SHALL have no finding.

#### Scenario: kubeconform is not installed
- **WHEN** no directory of PATH holds kubeconform, and the adapter validates a manifest
- **THEN** the outcome status is `unavailable`, the reason is `Binary 'kubeconform' not found on PATH`, and the outcome has no finding

### Requirement: Trivy's misconfiguration scan is the IaC scanner of the registry
The scanner registry SHALL hold `trivy-config`, which runs `trivy config <target> --severity <severities> --format json --quiet` with the Trivy that `tools.lock` pins, and SHALL hold no Checkov adapter. Every scanner of the registry that has a binary in `tools.lock` SHALL have no built-in patterns.

#### Scenario: devops scan report scans IaC files with Trivy
- **WHEN** `devops scan report` runs every registered scanner over a directory
- **THEN** Trivy starts once with `fs` and once with `config`, and no scanner named `checkov` runs
