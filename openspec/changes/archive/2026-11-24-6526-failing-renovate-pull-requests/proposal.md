# Proposal: #6526

## Why

Multiple Renovate pull requests fail continuous integration checks.
PR #6914 fails PR title length checks because the package topic is too long.
PR #6918 fails because PyPI published broken epoch releases of `grafana-foundation-sdk`.
PR #6919 fails because Debian Trixie images do not support Node 26.
PR #6917 fails because Python 3.15 runtime is not supported by dependencies.
PR #6913 fails because Renovate updates the runtime lower bound `requires-python` on patch releases.
PR #6909 fails because OpenSpec 2.1.1 enforces strict length limits on requirement descriptions.

## What Changes

- Add `"commitMessageTopic": "searxng"` in `.github/renovate.json` for SearXNG rules.
- Add `"allowedVersions": "<25.0.0"` for Node in `.github/renovate.json`.
- Add `"allowedVersions": "<3.15.0"` and dashboard approval for Python runtime in `.github/renovate.json`.
- Disable `requires-python` updates from PEP 621 manager in `.github/renovate.json`.
- Add `"allowedVersions": "<1.0.0"` for `grafana-foundation-sdk` in `.github/renovate.json`.
- Shorten requirement texts in active OpenSpec changes `3060` and `3429` below 500 characters.

## Capabilities

### Modified
- `renovate-rules`: The Renovate configuration restricts incompatible dependency versions.
- `openspec-specs`: Active change requirements comply with OpenSpec 2.1.1 strict limits.

## Impact

Automated Renovate pull requests pass pull request title checks and quality gates without manual repairs.

## Feasibility

Confirmed against real CI runs: Renovate PRs #6914, #6918, #6919, #6917, #6913, and #6909 failed with these specific errors.
All checks pass with these configuration and specification updates.

## Existing Tool Considered

Renovate is the open and maintained dependency automation tool.
Configuration updates configure Renovate directly.
No custom code is built.
