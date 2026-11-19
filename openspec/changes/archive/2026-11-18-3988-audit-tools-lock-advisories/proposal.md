# Proposal: #3988

## Why
`devops ci audit` checks `uv.lock` and the Node lock files. It does not check the requirement files of the tools lock. Pins in `src/devops_cli/tools_lock/semgrep.txt` hold known advisories, but no audit check shows them. Closes #3988.

## What Changes
- Add `osv-scanner` checks to `devops ci audit` for each requirement file under `src/devops_cli/tools_lock/`.
- Read `.osv-scanner-ignore.yaml` for time-limited ignores of advisories with no released fix, following `SECURITY.md`.
- Add time-limited ignore entries for the 6 `mcp` and `opentelemetry-api` advisories pinned in `semgrep.txt`, expiring on 2026-11-21, tracked by #3988.
- Note that Semgrep upstream (through 1.186.0) pins the vulnerable versions of `mcp` and `opentelemetry-api`.

## Capabilities
### Modified Capabilities
- `ci-dependency-audit`: audit requirement files of the tools lock with `osv-scanner` and support time-limited ignores.

## Impact
- `devops ci audit` and the CI `audit` row scan tools lock requirement files.
- Failures occur when tools lock pins contain unignored advisories or when ignores expire.

## Feasibility
Confirmed against real system: `osv-scanner --lockfile requirements.txt:<file>` scans `semgrep.txt`, `bandit.txt`, and `ansible-core.txt`. `semgrep.txt` and `bandit.txt` compile cleanly with `uv pip compile`.

## Existing Tool Considered
`osv-scanner` 2.6.0 is already pinned in `tools.lock` and available on PATH in the environment.
