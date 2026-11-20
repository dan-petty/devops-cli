## MODIFIED Requirements

### Requirement: kubeconform reads the one report object that it writes
The kubeconform adapter SHALL run the kubeconform on PATH with `-output json`. The parser SHALL give one HIGH finding at `<manifest>:<Kind>/<name>` for each resource with the status `statusInvalid` or `statusError`. It SHALL give no finding for `statusValid` or `statusSkipped`.

#### Scenario: kubeconform finds two invalid resources and one it cannot validate
- **WHEN** kubeconform 0.8.0 validates a manifest directory and exits 1. It reports the ConfigMap `settings` and the Service `web` as `statusInvalid`, and the Widget `blue` as `statusError`
- **THEN** the scan ran, and its findings are three HIGH findings, at `k8s/app.yaml:Widget/blue`, `k8s/app.yaml:ConfigMap/settings` and `k8s/app.yaml:Service/web`, in the order of the report

#### Scenario: A verbose report also lists valid and skipped resources
- **WHEN** the parser reads a kubeconform 0.8.0 `-verbose` report with one resource of each status
- **THEN** the findings are two HIGH findings, for the `statusError` resource and the `statusInvalid` resource

#### Scenario: kubeconform finds nothing
- **WHEN** kubeconform writes `{"resources": []}` and exits 0
- **THEN** the scan ran and has no finding

### Requirement: Trivy's misconfiguration scan is the IaC scanner of the registry
The scanner registry SHALL hold `trivy-config`, which runs `trivy config <target> --severity <severities> --format json --quiet` with the Trivy on PATH, and SHALL hold no Checkov adapter. No scanner of the registry SHALL have built-in patterns that stand in for a missing program.

#### Scenario: devops scan report scans IaC files with Trivy
- **WHEN** `devops scan report` runs every registered scanner over a directory
- **THEN** Trivy starts once with `fs` and once with `config`, and no scanner named `checkov` runs

## REMOVED Requirements

### Requirement: Every scanner of the registry has a pinned program
**Reason**: The devtools image installs each scanner on PATH, and devops-cli is no package manager (#4363). The test compared the registry with `tools.lock`, which is gone.
**Migration**: A scanner with no program on PATH gives no result and no built-in pattern, as the registry scan test shows.
