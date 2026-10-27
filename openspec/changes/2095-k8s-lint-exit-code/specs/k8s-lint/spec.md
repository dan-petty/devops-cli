# k8s-lint Specification

## Purpose
The `devops k8s lint` command audits a manifest or Helm chart with Kube-linter, reports what it found, and sets its exit code as the gate: a pass only when Kube-linter ran and found nothing.

## ADDED Requirements

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
