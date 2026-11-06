# Proposal

## Why

Issue #3705: `uv audit` reports GHSA-3jp2-3mrg-2vxc (CVE-2026-49272) for `oauthlib` 4.0.0, so the `audit` check fails on each pull request. `oauthlib` is a transitive dependency: `kubernetes` needs `requests-oauthlib`, and that package needs `oauthlib`.

## What Changes

- Run `uv lock --upgrade-package oauthlib`. The lock moves `oauthlib` from 4.0.0 to 4.0.1. No other package changes.
- `pyproject.toml` stays the same, because the project does not import `oauthlib`.
- The change sets `skip_specs: true` in `.openspec.yaml`: no command, option or message changes.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Dependencies: `uv.lock`.

## Feasibility

- Command output on origin/main at f481be8c: `uv audit --frozen` gives `oauthlib 4.0.0 has 1 known vulnerability`, and it names GHSA-3jp2-3mrg-2vxc.
- The OSV query for `oauthlib` 4.0.0 returns this advisory. The query for 4.0.1 returns no advisory.
- The audit output of the Static Analysis job of pull request #3704, on 2026-11-06, says `Fixed in: 4.0.1`. The GitHub advisory database published the advisory again on 2026-11-05 at 21:01 UTC, and the audit reported it after that time. So a lock at 4.0.0 does not pass.
- PyPI lists `oauthlib` 4.0.1, uploaded on 2026-10-31.
- Command output: `uv lock --upgrade-package oauthlib` gives `Updated oauthlib v4.0.0 -> v4.0.1`, and `uv audit --frozen` then gives `Found no known vulnerabilities`.

## Existing Tool Considered

Built-in `uv lock` and `uv audit`. An ignore for the advisory is rejected: only the owner can lower a security threshold.
