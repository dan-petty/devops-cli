# Task 419: Publish Scanner Findings to Code Scanning

**Issue**: [#419](https://github.com/dan-petty/devops-cli/issues/419)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

`devops scan` already normalizes Trivy, Gitleaks, Semgrep, Checkov and Kubeconform output and writes SARIF 2.1.0 (`src/devops_cli/security/sarif.py:write_sarif`, called from `commands/scan.py:839`). Nothing uploads it. `security-events: write` appears in exactly one workflow — `codeql.yml` — so the only findings that reach a pull request are CodeQL's, and five scanners' results terminate in a CI log or a local file. A log is where a finding goes to be ignored: nobody opens it unless the build is already red, and an advisory finding never turns it red.

#### Key Deliverables:
- Context & Rationale*: `devops scan` already normalizes Trivy, Gitleaks, Semgrep, Checkov and Kubeconform output and writes SARIF 2.1.0 (`src/devops_cli/security/sarif.py:write_sarif`, called from `commands/scan.py:839`). Nothing uploads it. `security-events: write` appears in exactly one workflow — `codeql.yml` — so the only findings that reach a pull request are CodeQL's, and five scanners' results terminate in a CI log or a local file. A log is where a finding goes to be ignored: nobody opens it unless the build is already red, and an advisory finding never turns it red.
- Deliverable*: Upload the scan SARIF from CI under its own `category`, so each scanner's alerts are attributed and de-duplicated across runs. The emitter exists; this is the publication step alone.
- Constraint*: A run that finds nothing must still be uploaded. Code scanning resolves an alert only when the tool that raised it reports again without it, so a scanner that stops appearing leaves every alert it ever raised open indefinitely. Fingerprints must also exclude the line number, or an unrelated edit above a finding re-alerts it.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
