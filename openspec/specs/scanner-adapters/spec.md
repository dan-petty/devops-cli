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
