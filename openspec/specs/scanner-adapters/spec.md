# scanner-adapters Specification

## Purpose
How the scanner adapters of `devops_cli.security` start Gitleaks, Popeye and Pluto with the flags that each tool takes, and read the report that each tool writes, so that a scan that finds something is never read as a failed scan or a clean scan.

## Requirements

### Requirement: Gitleaks writes its report on stdout, with each secret redacted
The Gitleaks adapter SHALL run `gitleaks dir --report-format json --report-path - --redact <path>` to scan files, and `gitleaks git --report-format json --report-path - --redact <path>` to scan the history of a repository. A run that exits 1 with a JSON report that holds findings SHALL be a scan that ran, with one finding for each item of the report.

#### Scenario: Gitleaks finds a leak
- **WHEN** Gitleaks scans a file, exits 1, and writes a report with one `github-pat` item at line 1
- **THEN** the scan ran, and its one finding is CRITICAL, at `<file>:1`, with the title `[GITLEAKS:github-pat] <description>`

#### Scenario: Gitleaks finds nothing
- **WHEN** Gitleaks scans a file, exits 0, and writes `[]`
- **THEN** the scan ran and has no finding

#### Scenario: The agent tool reports the leak
- **WHEN** the agent calls `scan_gitleaks` over a file in which Gitleaks finds a leak
- **THEN** the reply is `Gitleaks scan status: ok`, then `Findings (1):`, then the line of the finding

### Requirement: Popeye reports warnings and errors over the namespace that it gets
The Popeye adapter SHALL run `popeye -o json -l warn`, followed by `-A` when it gets no namespace, by `-n <namespace>` when it gets a namespace, and by `--context <context>` when it gets a context other than the current one. The parser SHALL read `popeye.sections` and SHALL give one finding for each issue: at `k8s:<linter>/<namespace>/<name>`, followed by `/<group>` when the group names a container, with the message as its title, and with the severity MEDIUM for level 2 and HIGH for level 3.

#### Scenario: Popeye reports issues of a resource and of its container
- **WHEN** Popeye runs over the namespace `argocd`, exits 1, and reports a level 3 issue and a level 2 issue of the Deployment `argocd/argocd-applicationset-controller`, and a level 2 issue of its container `applicationset-controller`
- **THEN** the scan ran, the command is `popeye -o json -l warn -n argocd`, and the findings are a HIGH and a MEDIUM finding at `k8s:deployments/argocd/argocd-applicationset-controller` and a MEDIUM finding at `k8s:deployments/argocd/argocd-applicationset-controller/applicationset-controller`

#### Scenario: Popeye gets no namespace
- **WHEN** the adapter runs Popeye with no namespace
- **THEN** the command is `popeye -o json -l warn -A`

### Requirement: Pluto names its target relative to its working directory
The Pluto adapter SHALL name its target relative to the directory that the command starts in, because Pluto writes each `filePath` as that directory joined to the path that it read. The parser SHALL name the manifest by the normalized `filePath`.

#### Scenario: A review runs Pluto from its scratch directory
- **WHEN** a review runs Pluto over a manifest from a scratch directory outside the tree
- **THEN** the command names the manifest by its path relative to the scratch directory, and a `filePath` that climbs out of the scratch directory with `..` names the manifest

### Requirement: A Pluto finding reports only what Pluto writes
The parser SHALL give one finding for each item of a Pluto report, at `<manifest>:<Kind>/<namespace>/<name>`, or `<manifest>:<Kind>/<name>` when the item has no namespace. A finding SHALL be HIGH for a removed API and MEDIUM for a deprecated API, SHALL name the release that removed or deprecated it, and SHALL name the replacement API, or say that Kubernetes has no replacement API when `replacement-api` is empty. The parser SHALL invent no kind, API or replacement.

#### Scenario: Pluto finds two removed APIs, one with no replacement
- **WHEN** Pluto runs over a manifest directory and reports the Deployment `shop/web` on `extensions/v1beta1` and the PodSecurityPolicy `restricted` on `policy/v1beta1`, both removed, the second with an empty `replacement-api`
- **THEN** the command starts in that directory with `-d .`, and the findings are HIGH at `deploy.yaml:Deployment/shop/web` with the fix `Change apiVersion from extensions/v1beta1 to apps/v1.`, and HIGH at `deploy.yaml:PodSecurityPolicy/restricted` with the fix `Remove PodSecurityPolicy 'restricted': no Kubernetes API replaces policy/v1beta1.`

### Requirement: uv audit audits the lockfile as it is
The uv audit adapter SHALL start `uv audit --frozen --quiet --output-format json` in the directory that it scans, so that uv audits the `uv.lock` of the project as it is and does not write it.

#### Scenario: The adapter scans a project directory
- **WHEN** the uv audit adapter scans a project directory
- **THEN** uv starts in that directory with `uv audit --frozen --quiet --output-format json`

### Requirement: uv audit reports each finding of its report
The uv audit adapter SHALL give one finding for each vulnerability of the JSON report of uv, at `uv.lock:<package>`, with the advisory id and the summary in its title and the releases that fix it in its fix. It SHALL give one finding for each adverse project status of the report.

#### Scenario: uv audit finds vulnerabilities and adverse statuses
- **WHEN** uv audit exits 1 and reports a vulnerability of urllib3 1.26.5 that the releases 1.26.19 and 2.2.2 fix, a vulnerability `PYSEC-2024-60` of idna 3.6 with no summary and no fix release, and the adverse statuses `archived` of `legacy-lib` and `quarantined` of `suspect-lib`
- **THEN** the outcome is `ran` with four findings at the severity `MEDIUM`: the fix of the first is `Upgrade urllib3 from 1.26.5 to 1.26.19 or 2.2.2`, the title of the second is `[PYSEC-2024-60] idna 3.6 has a known vulnerability`, and the titles of the last two are `[archived] legacy-lib is archived on its index` and `[quarantined] suspect-lib is quarantined on its index`

#### Scenario: uv audit finds nothing
- **WHEN** uv audit exits 0 with a report of no vulnerability and no adverse status
- **THEN** the outcome is `ran` with no finding

### Requirement: A uv audit run with no project report is a failed scan
The uv audit adapter SHALL read a run that writes no report and exits non-zero as a failed scan, with what uv wrote on stderr as the reason. It SHALL read a report with no `vulnerabilities` list or no `adverse_statuses` list as a failed scan, and not as a scan that found nothing.

#### Scenario: The project has no lockfile
- **WHEN** uv audit exits 1, writes no report, and writes "error: Unable to find lockfile at `uv.lock`" and the rest of its message on stderr
- **THEN** the outcome is `failed`, with a reason that is `Scanner exited with code 1:` and then the message of uv

#### Scenario: The report has another layout
- **WHEN** uv audit exits 0 and writes a report with no `vulnerabilities` list and no `adverse_statuses` list
- **THEN** the outcome is `failed` with no finding, and its reason starts with `Scanner execution failed:`

### Requirement: uv audit scans only a directory
The uv audit adapter SHALL NOT start uv for a path that is not a directory, such as a directory that does not exist or a file. It SHALL give the outcome `not_applicable` with a reason that names the path, so that uv does not audit the project of a parent directory as the project of that path.

#### Scenario: The directory does not exist
- **WHEN** the uv audit adapter scans the path `services/api-typo` of a project, and no directory is at that path
- **THEN** uv does not start, and the outcome is `not_applicable` with no finding and the reason `<path> is not a directory. uv audit audits the project of a directory.`

#### Scenario: The path is a file
- **WHEN** the uv audit adapter scans the `uv.lock` file of a project
- **THEN** uv does not start, and the outcome is `not_applicable` with no finding and the reason `<path> is not a directory. uv audit audits the project of a directory.`

### Requirement: kubeconform reads the one report object that it writes
The kubeconform adapter SHALL run the kubeconform that `tools.lock` pins with `-output json`. The parser SHALL give one HIGH finding at `<manifest>:<Kind>/<name>` for each resource with the status `statusInvalid` or `statusError`. It SHALL give no finding for `statusValid` or `statusSkipped`.

#### Scenario: kubeconform finds two invalid resources and one it cannot validate
- **WHEN** kubeconform 0.8.0 validates a manifest directory and exits 1. It reports the ConfigMap `settings` and the Service `web` as `statusInvalid`, and the Widget `blue` as `statusError`
- **THEN** the scan ran, and its findings are three HIGH findings, at `k8s/app.yaml:Widget/blue`, `k8s/app.yaml:ConfigMap/settings` and `k8s/app.yaml:Service/web`, in the order of the report

#### Scenario: A verbose report also lists valid and skipped resources
- **WHEN** the parser reads a kubeconform 0.8.0 `-verbose` report with one resource of each status
- **THEN** the findings are two HIGH findings, for the `statusError` resource and the `statusInvalid` resource

#### Scenario: kubeconform finds nothing
- **WHEN** kubeconform writes `{"resources": []}` and exits 0
- **THEN** the scan ran and has no finding

### Requirement: kubeconform validates only the manifests of the target
The kubeconform adapter SHALL give kubeconform only the path of each Kubernetes manifest of the target that git lists and does not ignore. When the target holds no manifest, the scan SHALL be `not_applicable`, and kubeconform SHALL NOT start.

#### Scenario: A directory holds manifests and other YAML and JSON files
- **WHEN** the adapter validates a directory with a manifest and other YAML and JSON files. The other files are a Helm values file, a Helm template, a dashboard, a workflow, a package file, and a manifest that git ignores
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
