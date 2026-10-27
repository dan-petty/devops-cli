# Proposal

## Why

Issue #2344: Update the pinned uv and Python versions to uv 0.13.6 and Python 3.14.10.
The uv pins disagree today: the `Dockerfile` and `.devcontainer/Dockerfile` pin 0.12.23, and the setup-toolchain action pins 0.13.5.
After this change, all three places pin the same uv release.

Issue #2347: `uv audit` reports GHSA-6v38-4h7w-rj9h for `authlib 1.8.0`, and the `audit` check fails on every pull request. The lock moves to a fixed release in the same pull request, because the pull request cannot pass the required checks without it.

## What Changes

- Update `.python-version` from `3.14.9` to `3.14.10`.
- Update uv to `0.13.6` in `.github/actions/setup-toolchain/action.yml`, `Dockerfile` (with the new image digest) and `.devcontainer/Dockerfile`.
- Update the placeholder version in `.github/ISSUE_TEMPLATE/bug_report.yml` and the fixture in `tests/test_uv.py` to `3.14.10`.
- Upgrade `authlib` from `1.8.0` to `1.9.1` in `uv.lock` with `uv lock --upgrade-package authlib`. No other package changes, so no package with a linked version moves.
- The change sets `skip_specs: true` in `.openspec.yaml`: no command, option or message changes.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Runtime: `.python-version`, `uv.lock`.
- Toolchain: `.github/actions/setup-toolchain/action.yml`, `Dockerfile`, `.devcontainer/Dockerfile`.
- Issue Templates: `.github/ISSUE_TEMPLATE/bug_report.yml`.
- Tests: `tests/test_uv.py`.

## Feasibility

- uv 0.13.6 is a release of astral-sh/uv, and the image `ghcr.io/astral-sh/uv:0.13.6` exists. Its digest comes from the ghcr.io manifest.
- Command output: uv 0.12.23 stops with `No download found for request: cpython-3.14.10-linux-x86_64-gnu`. uv 0.13.6 installs `cpython-3.14.10-linux-x86_64-gnu`.
- Command output: `uv lock --check` passes under uv 0.13.6 with Python 3.14.10.
- Command output: `uv lock --upgrade-package authlib` gives `Updated authlib v1.8.0 -> v1.9.1`. `uv audit` then gives `Found no known vulnerabilities`. The advisory names 1.9.0 as the fixed release.

## Existing Tool Considered

Built-in `uv` toolchain and the `astral-sh/setup-uv` action.
