# Proposal: #6419

## Why
The project runs `devops ci audit` with a custom ignore loader, models, filter, and messages for `.npm-audit-ignore.yaml`. `npm audit` reads no native configuration file. osv-scanner has a native configuration file (`osv-scanner.toml`) for ignored vulnerabilities. The project can scan the root `package-lock.json` with osv-scanner directly and drop custom loaders.

## What Changes
- Delete `.npm-audit-ignore.yaml` and the custom npm ignore loader, filter, models, messages, and constants.
- Scan the root `package-lock.json` with `osv-scanner scan source --lockfile package-lock.json` instead of `npm audit`.
- Add `osv-scanner.toml` and validate it with a `check-jsonschema` pre-commit hook using `osv-scanner.schema.json`.
- Keep the security rule that requires an expiry date, a tracking issue reason (`#N`), and refuses wildcard advisory IDs.
- Update `SECURITY.md`, `docs/ROUTINE_TASKS.md`, and `docs/SDLC.md` to reference `osv-scanner` and `osv-scanner.toml`.

## Capabilities
- Native vulnerability ignores via `osv-scanner.toml` `[[IgnoredVulns]]`.
- Pre-commit schema enforcement on native configuration files.

## Impact
- Eliminates custom ignore loading code and reduces maintenance surface.
- Harmonizes vulnerability scanning on lockfiles with `osv-scanner`.

## Feasibility
- Verified `osv-scanner` v2 syntax `scan source --lockfile package-lock.json`.
- Tested `check-jsonschema` pre-commit hook against `osv-scanner.toml`.

## Existing Tool Considered
- `osv-scanner` native config `[[IgnoredVulns]]` replaces custom ignore parsing.
- `check-jsonschema` validates `osv-scanner.toml` against project schema constraints.
