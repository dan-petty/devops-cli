# Proposal: #6481

## Why

Issue #6481: since 2026-11-19 22:45 UTC, the `audit` row of the required check Static Analysis fails on each new pull request. osv-scanner names GHSA-qx49-fqc8-xw99 (HIGH, CVSS 7.5, fixed in `mcp` 1.30.0) for `mcp==1.29.0` in `src/devops_cli/tools_lock/semgrep.txt`. No released Semgrep takes the fix, so SECURITY.md "A Finding with No Fix" lets an agent add a 3-day entry.

## What Changes

- Add one entry to `.osv-scanner-ignore.yaml`: the id GHSA-qx49-fqc8-xw99, the path `src/devops_cli/tools_lock/semgrep.txt`, a statement that gives the reason and the tracking issue #6480, and `expired_at: 2026-11-22`.
- The change has no spec delta and sets `skip_specs: true`: it changes only the configuration of a scanner.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `.osv-scanner-ignore.yaml`, which `devops ci audit` reads in Static Analysis.
- No tool pin and no lock file changes.

## Feasibility

Read on 2026-11-19 against `origin/main` at `bc57c1ee9`.

- Check run 135948694190 (Static Analysis of #6472): `✗ fail [audit]`, with the row `GHSA-qx49-fqc8-xw99 | 7.5 | PyPI | mcp | 1.29.0 | 1.30.0 | src/devops_cli/tools_lock/semgrep.txt`. The other advisories of that file show as ignored until 2026-11-21.
- `https://api.osv.dev/v1/vulns/GHSA-qx49-fqc8-xw99`: severity HIGH, reviewed and published 2026-11-19 22:45 UTC. Affected ranges: 1.9.1 to before 1.30.0, and 2.0.0a1 to before 2.2.0.
- `https://pypi.org/pypi/semgrep/json`: the newest release is 1.186.0 (2026-11-18), and its `requires_dist` holds `mcp==1.29.0`. Thus no released Semgrep takes `mcp` 1.30.0.
- `uv run devops ci --check --only audit` on the base fails with the same row, and passes with the entry of this change.

## Existing Tool Considered

osv-scanner and its ignore file are the open tools. The change builds no code.
