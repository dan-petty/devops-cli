## REMOVED Requirements

### Requirement: Audit scans the tools lock requirement files
**Reason**: The tools lock and its requirement files are gone (#4363). The devtools repository audits the locks of the tools that its image installs.
**Migration**: None in this repository. `uv audit` and the `npm audit` of the root `package-lock.json` stay.

### Requirement: Audit fails on an advisory
**Reason**: It held the `osv-scanner` audit of the requirement files of the tools lock, which are gone (#4363).
**Migration**: None in this repository.

### Requirement: Tools lock finding with an active ignore entry passes
**Reason**: `.osv-scanner-ignore.yaml` named only requirement files of the tools lock, which are gone (#4363).
**Migration**: An advisory of the root `package-lock.json` keeps `.npm-audit-ignore.yaml`.

### Requirement: Semgrep release is named
**Reason**: The Semgrep pin of the tools lock is gone (#4363). The devtools repository holds the Semgrep of its image.
**Migration**: None in this repository.
