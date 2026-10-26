# Proposal

## Why

Issue #2317: Update the pinned Python runtime and CI toolchain to Python 3.14.9.
Python 3.14.9 provides critical security fixes for intermediate CA trust chains and bug fixes.
Supporting Python 3.14.9 in CI requires updating `uv` to `0.13.5` in the GitHub Actions toolchain action.

## What Changes

- Update `.python-version` from `3.14.7` to `3.14.9`.
- Update `version: "0.12.16"` to `version: "0.13.5"` in `.github/actions/setup-toolchain/action.yml`.
- Update placeholder version in `.github/ISSUE_TEMPLATE/bug_report.yml` to `3.14.9`.
- Update test fixture runtime version in `tests/test_uv.py` to `3.14.9`.
- The change sets `skip_specs: true` in `.openspec.yaml`: no command, option or message changes.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Runtime: `.python-version`.
- CI Toolchain: `.github/actions/setup-toolchain/action.yml`.
- Issue Templates: `.github/ISSUE_TEMPLATE/bug_report.yml`.
- Tests: `tests/test_uv.py`.

## Feasibility

- Confirmed against CPython 3.14.9 runtime and uv 0.13.5.
- `uv python list --only-downloads` under uv 0.13.5 provides `cpython-3.14.9-linux-x86_64-gnu`.
- All 19 checks of `devops ci --check` pass under Python 3.14.9.

## Existing Tool Considered

Built-in `uv` toolchain and GitHub Actions `astral-sh/setup-uv` composite action.
