# Proposal

## Why

Issue #2786: `uv audit` reports GHSA-9pg5-8c7x-5hfx (CVE-2026-119284) for `joserfc 1.7.5`. A compact JWS size guard allocates attacker-controlled segments before it rejects them. The `audit` check fails on every pull request and on `main`. The lock must move to a fixed release before any pull request can pass the required checks.

`joserfc` is not a direct dependency. `authlib 1.9.1` needs it. `fastmcp-slim` (`client` and `server` extras) and `pydantic-ai-slim` (`mcp` extra) need `authlib`.

## What Changes

- Upgrade `joserfc` from `1.7.5` to `1.7.7` in `uv.lock` with `uv lock --upgrade-package joserfc`. No other package changes, and `pyproject.toml` gets no new constraint.
- The change sets `skip_specs: true` in `.openspec.yaml`. No command, option or message changes. Only a transitive dependency of the lock moves.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Runtime: `uv.lock`.

## Feasibility

- OSV record of GHSA-9pg5-8c7x-5hfx (`https://api.osv.dev/v1/vulns/GHSA-9pg5-8c7x-5hfx`): the PyPI package `joserfc` is affected from `0` and fixed in `1.7.6`.
- Command output: `uv audit` on the lock gives `joserfc 1.7.5 has 1 known vulnerability` and `Fixed in: 1.7.6`.
- Command output: `uv tree --invert --package joserfc` shows `authlib v1.9.1` as the only parent. `authlib` sets no upper bound on `joserfc`.
- Command output: `uv lock --upgrade-package joserfc --dry-run` gives `Update joserfc v1.7.5 -> v1.7.7` and no other change. The lock can move to a fixed release without a constraint.

## Existing Tool Considered

`uv lock --upgrade-package` and `uv audit`. Renovate does not manage the Python lock. Nothing is built, and no internal code is deleted.
