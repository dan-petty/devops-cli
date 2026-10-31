# Proposal

## Why

Issue #2808: `uv audit` reports 5 known vulnerabilities in the lock: GHSA-mpqx-q82w-9x46 for `graphql-core 3.3.0` and four for `pyasn1 0.6.4`. All are denial of service. The `audit` check fails on every pull request and on `main`. The lock must move to fixed releases before a pull request can pass the required checks. Issue #2810 reports the same failure.

`pyasn1` is not a direct dependency. `graphql-core` is a direct dependency, pinned to `==3.3.0` in `pyproject.toml`.

## What Changes

- Upgrade `pyasn1` from `0.6.4` to `0.6.5` in `uv.lock` with `uv lock --upgrade-package pyasn1`. No constraint is added.
- Raise the pin of `graphql-core` from `==3.3.0` to `==3.3.1` in `pyproject.toml`, and lock it.
- The change sets `skip_specs: true` in `.openspec.yaml`. No command, option or message changes.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Runtime: `pyproject.toml`, `uv.lock`.

## Feasibility

- Command output: `uv audit` on the lock gives `graphql-core 3.3.0 has 1 known vulnerability` with `Fixed in: 3.3.1`, and the fixed release for `pyasn1` is `0.6.5`.
- Command output: `uv lock --upgrade-package pyasn1` gives `Updated pyasn1 v0.6.4 -> v0.6.5` and no other change. `uv audit` then reports only `graphql-core`.
- Command output: `uv tree --invert --package graphql-core` shows only `devops-cli` as the parent, so the exact pin is the only constraint to raise.
- Command output: after the bump, `uv audit` gives `Found no known vulnerabilities`, and the 187 tests of the GraphQL request classifier and the rate limiter pass.

## Existing Tool Considered

`uv lock --upgrade-package` and `uv audit`. Renovate does not manage the Python lock. Nothing is built, and no internal code is deleted.
