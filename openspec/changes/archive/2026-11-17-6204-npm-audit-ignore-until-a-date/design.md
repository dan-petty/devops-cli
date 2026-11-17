# Design

## Decisions
- The ignore file has the form of the `vulnerabilities` entries of `.trivyignore.yaml`, and `expired_at` has Trivy's meaning: the entry applies before that day and not on it.
- `audit_verdict` takes the advisory IDs that apply to the command. An npm report of findings is clean only when that set holds every advisory of the report. A report with no advisory objects stays a finding.
- The lockfile of an `npm audit` command is its `--prefix` with `package-lock.json`, which `npm_audit_lockfile` reads from the command that `build_npm_audit_cmd` builds.
- The gate's `audit` row and `devops ci audit` both print a line for each entry they used and each that expired. When every finding is ignored, the gate row passes with those lines.
- The model of an entry refuses a wildcard in the ID or a path and a statement with no `#N`, so the rules of SECURITY.md hold for each entry.

## Rejected alternatives
- Lower the npm audit level to critical: SECURITY.md forbids a lower threshold.
- Downgrade OpenSpec to 1.14.2, which `npm audit` offers: it drops two releases of OpenSpec and its skills, and only moves the finding.
- Put the entry in `.trivyignore.yaml`: Trivy reads that file for `trivy config` only, and one file for two scanners hides which scanner reads an entry.
