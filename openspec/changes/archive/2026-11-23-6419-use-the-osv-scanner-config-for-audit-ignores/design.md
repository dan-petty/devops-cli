# Design: #6419

## Context
`devops ci audit` scanned `uv.lock` with `uv audit` and the root `package-lock.json` with `npm audit`. Because `npm audit` reads no configuration file for ignores, `devops-cli` maintained custom YAML parsing and filtering logic. `osv-scanner` supports a native `osv-scanner.toml` with `[[IgnoredVulns]]`.

## Goals
- Remove custom ignore parsing and filtering code for npm advisories.
- Audit the root `package-lock.json` with `osv-scanner scan source --lockfile package-lock.json`.
- Enforce mandatory expiry and issue tracking on `osv-scanner.toml` via `check-jsonschema`.
- Ensure `devops ci audit` passes and accurately interprets `osv-scanner` exit codes (1 for vulnerabilities, other non-zero for failure to run).

## Decisions
- **`osv-scanner` v2 command**: Build `[BIN_OSV_SCANNER, "scan", "source", "--lockfile", str(lockfile)]` in `config/commands.py` as `build_osv_audit_cmd`.
- **Verdict reader**: Map `BIN_OSV_SCANNER` in `_FAILURE_READERS` to return `AuditVerdict.VULNERABLE` for exit code 1 and `AuditVerdict.NOT_RUN` for any other code.
- **Pre-commit schema**: Add `check-jsonschema` hook in `.pre-commit-config.yaml` validating `osv-scanner.toml` against `osv-scanner.schema.json`.

## Risks and Mitigations
- *Risk*: `osv-scanner.toml` ignores could be added without expiry or reason.
  *Mitigation*: Pre-commit schema enforcement requires `effectiveUntil`, a regex matching `#\\d+` in `reason`, and forbids `*` in `id`.
