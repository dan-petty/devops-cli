# Proposal

## Why

Issue #2349: `uv audit` reports GHSA-45c3-73f7-pv4m (CVE-2026-114605) for `dnspython 2.8.0`: `dns.name.from_wire_parser()` uses too much CPU. The `audit` check fails on every pull request and on the release pull request #2329. The advisory names 2.9.0 as the fixed release.

## What Changes

- Pin `dnspython[idna]==2.9.0` in `pyproject.toml` and run `uv lock`. The lock moves `idna` from 3.19 to 3.20, the release that the `idna` extra of `dnspython` 2.9.0 resolves to. No other package changes.
- The change sets `skip_specs: true` in `.openspec.yaml`: no command, option or message changes.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Dependencies: `pyproject.toml`, `uv.lock`.

## Feasibility

- Command output in CI on pull request #2329: `dnspython 2.8.0 has 1 known vulnerability ... Fixed in: 2.9.0`.
- Command output: `uv lock` gives `Updated dnspython v2.8.0 -> v2.9.0` and `Updated idna v3.19 -> v3.20`. `uv audit` then gives `Found no known vulnerabilities`.
- PyPI lists `dnspython` 2.9.0 with `requires-python >=3.11`.

## Existing Tool Considered

Built-in `uv lock` and `uv audit`. An ignore for the advisory is rejected: only the owner can lower a security threshold.
