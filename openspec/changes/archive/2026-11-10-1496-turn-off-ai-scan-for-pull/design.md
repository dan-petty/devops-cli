# Design

## Context

See proposal.md for the problem context (#1496). AI Scan for pull requests consumed AI quota rapidly.

## Goals / Non-Goals

**Goals:**
- Turn off AI Scan for pull requests to prevent quota exhaustion.
- Document the setting and read-back commands in ADR 0004.

**Non-Goals:**
- Modify GitHub Actions workflow definitions or CodeQL configuration.
- Change CLI commands or runtime code.

## Decisions

### 1. Disable AI Scan via GitHub API

- **Decision**: Update repository setting `code-scanning/ai-scan` with `pr_scan=disabled` via GitHub API.
- **Alternative considered**: Disable through the GitHub web UI only.
  - *Rejected*: An API call provides deterministic execution and verifiable programmatic read-back.

### 2. Document read-back commands in ADR 0004

- **Decision**: Update decision D6 of ADR 0004 to record `pr_scan: disabled` and provide the exact `gh api` commands to inspect both AI Scan and ruleset review settings.
- **Alternative considered**: Create a new ADR for AI Scan.
  - *Rejected*: ADR 0004 already governs pull request gates and Copilot review boundaries. Adding the setting to decision D6 keeps related policy in one place.

## Rejected Alternatives

None beyond the options detailed in Decisions above.
