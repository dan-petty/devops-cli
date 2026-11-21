## ADDED Requirements

### Requirement: A review in the runner pod fails closed when a scanner is missing
`devops review` in the pod of a runner Job SHALL list each review scanner that its files need and that the image does not hold as not installed, SHALL keep the findings of the scanners that ran, and SHALL exit 1. A review in that pod whose needed scanners all ran SHALL exit 0 and SHALL list no scanner as not installed.

#### Scenario: A scanner absent from the runner image
- **WHEN** `devops review` runs on a sample diff in the pod of a runner Job and Gitleaks is not on PATH
- **THEN** the report lists Gitleaks as not installed, the command exits 1, and the findings of the scanners that ran are still in the report

#### Scenario: Every scanner in the runner image
- **WHEN** `devops review` runs on a sample diff in the pod of a runner Job with every review scanner on PATH
- **THEN** the command exits 0 and the report lists no review scanner as not installed

## MODIFIED Requirements

### Requirement: A review runs its tools in the sandbox, or directly in the runner pod
`devops review path`, `devops review branch`, `devops review pr` and their MCP tools SHALL run every analyzer, evidence tool and canary in `SandboxToolExecutor`, except in the pod of a runner Job, where they SHALL run in `DirectToolExecutor`. An orchestrator, a mypy scan and a canary that get no executor SHALL use the sandbox. Each run SHALL record its executor, `sandbox` or `direct`. No option, config key or MCP parameter SHALL turn the sandbox off.

#### Scenario: A review that gets no executor
- **WHEN** an orchestrator that got no executor scans a Python file on a host that can start the sandbox
- **THEN** each command that starts a tool starts bubblewrap with the tool in it, and the record of each run names the executor `sandbox`

#### Scenario: A dry run
- **WHEN** a scan of Bandit, Gitleaks, Semgrep, Trivy, kube-linter, Pluto, osv-scanner, Ruff or mypy runs in a dry run
- **THEN** it starts no tool and gives its dry-run outcome

#### Scenario: A review in the runner pod
- **WHEN** `devops review` runs on a sample diff with the setting `roadmap.implement.in_runner` true
- **THEN** each scanner starts as a child of the review with no bubblewrap, the record of each run names the executor `direct`, and the report holds the findings of the scanners

## RENAMED Requirements

- FROM: `### Requirement: A review runs its tools in the sandbox and in no other place`
- TO: `### Requirement: A review runs its tools in the sandbox, or directly in the runner pod`
