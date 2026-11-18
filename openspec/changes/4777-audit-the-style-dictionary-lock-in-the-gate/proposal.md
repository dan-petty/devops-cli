# Proposal: #4777

## Why

The Style Dictionary lock at `src/devops_cli/tools_lock/style-dictionary/` is outside `tools.lock`, so the `audit` row of `devops ci` does not audit it and `devops install-tools` does not install it. `npm audit` of the lock reported findings in `glob` and `minimatch` and a low `deepmerge` finding that no release fixes. Closes #4777.

## What Changes

- Add `[npm.style-dictionary]` (version 5.8.0) to `src/devops_cli/tools_lock/tools.lock`, so the `audit` row audits the lock and `devops install-tools --tool style-dictionary` installs it.
- Override `glob` to 14.0.2 and `minimatch` to 11.0.1 in `src/devops_cli/tools_lock/style-dictionary/package.json`, and write the lock again. `npm audit` of the lock is then clean.
- Install Style Dictionary in the Design Tokens job of `.github/workflows/ci.yml` with `devops install-tools --tool style-dictionary`, and delete the hand `npm ci` step.
- Add `style-dictionary` to `NOT_IN_RUNNER` in `src/devops_cli/roadmap/runner_tools.py`, with the Design Tokens reason.
- Add a Renovate manager for the entry, and name the install and audit paths in `docs/DESIGN.md` and ADR 0024.
- The change alters a manifest entry, a lockfile, a CI workflow and documents. It adds no requirement to a capability, so it sets `skip_specs: true`.

## Capabilities

None. The existing `ci-dependency-audit` requirement audits the lockfile of each Node tool of the tools lock, and `tools-lock-install` covers each entry, so the added entry needs no delta.

## Impact

- The `audit` row audits the Style Dictionary lock, and it passes: the lock holds the fixed `glob` and `minimatch` and no `deepmerge` finding.
- `devops install-tools --tool style-dictionary` installs the lock, and the Design Tokens job uses it.

## Feasibility

- Read 2026-11-18 with npm 11.19.1 and Node 24.22.3: `npm audit --package-lock-only` of the lock reports only GHSA-3g3m-2fjr-6pw4 (glob, fixed in 14.0.2) and GHSA-g3hv-75wg-m249 (minimatch, fixed in 11.0.1); the `deepmerge` finding of the issue is no longer reported. After the overrides, `npm ci` installs glob 14.0.2 and minimatch 11.0.1, `npm audit` reports 0 findings, and `make design-tokens` exits 0 with unchanged outputs.
- The repository now reads `.npm-audit-ignore.yaml` for an `npm audit` finding with no fix (#6205), so the `osv-scanner` plan of the issue is out of date.

## Existing Tool Considered

- `npm audit` with the repository's `.npm-audit-ignore.yaml` (#6205) already audits each Node lock of the tools lock and carries a time-limited entry for a finding with no fix. The change uses it and adds no second scanner.
- `npm overrides` resolve `glob` and `minimatch` to the fixed releases, which SECURITY.md prefers over an ignore.
