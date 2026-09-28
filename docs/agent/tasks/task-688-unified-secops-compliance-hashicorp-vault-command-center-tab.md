# Task 688: Unified SecOps, Compliance & HashiCorp Vault Command Center (`tab-secops`)

**Issue**: [#688](https://github.com/dan-petty/devops-cli/issues/688)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/security`, `priority/p1-high`

---

## 1. Description & Objectives

Consolidates all static and dynamic security scanners into an actionable vulnerability triage center.

#### Key Deliverables:
- Context & Rationale*: Consolidates all static and dynamic security scanners into an actionable vulnerability triage center.
- Scanner Severity Dashboard*: Aggregated threat summary cards (Trivy CVEs by severity, Gitleaks detected secrets, Semgrep SAST alerts, Checkov IaC failed checks). Selecting an alert displays CVE details, affected line numbers, CVSS scores, and remediation hints.
- Automated Remediation Queue*: Highlights vulnerabilities resolvable via `devops scan fix` with one-key preview of auto-remediation patches.
- HashiCorp Vault Secret Broker Status*: Visual broker health indicator, seal state, token lease TTL progress bar, and OS Keyring synchronization status (`devops vault status`).
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
