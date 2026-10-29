# Proposal

## Why

Issue #1501: GitHub moves `ubuntu-latest` to Ubuntu 26.04 from 2026-10-19 (actions/runner-images#14748). The workflows pinned `ubuntu-24.04` in wait for the workflow linter to accept the `ubuntu-26.04` label. That blocker cleared when #1119 landed the maintained linter (#2687). This change re-pins every job to `ubuntu-26.04`.

## What Changes

- The 21 `runs-on: ubuntu-24.04` selections across the eight workflows (`.github/workflows/ci.yml`, `release.yml`, `codeql.yml`, `cleanup-devcontainer.yml`, `pr-title.yml`, `copilot-setup-steps.yml`, `fail-to-pass.yml`, `defect-pr-hardening-audit.yml`) become `runs-on: ubuntu-26.04`.
- The obsolete `# moves to ubuntu-26.04 in #1501` markers are removed; they pointed to this change.
- `tests/test_workflow_contracts.py` asserts the `audit-hardening` job runs on `ubuntu-26.04`.

The change re-pins the CI runners to the next Ubuntu image. It alters no `devops` command, option or message and touches no `devops` code, so it has no spec delta: `skip_specs: true`. It fits one pull request and deletes no internal code.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. No `devops` command, option or message changes.

## Impact

- CI: `.github/workflows/ci.yml`, `release.yml`, `codeql.yml`, `cleanup-devcontainer.yml`, `pr-title.yml`, `copilot-setup-steps.yml`, `fail-to-pass.yml`, `defect-pr-hardening-audit.yml`.
- Tests: `tests/test_workflow_contracts.py`.

## Feasibility

- The maintained linter `docker.io/kjanat/actionlint:1.17.0` (landed in #2687) accepts `ubuntu-26.04`. Confirmed by command output: running that image against a workflow with `runs-on: ubuntu-26.04` reports no `[runner-label]` error, and it lints the current eight workflows with zero errors.
- `ubuntu-26.04` is the next pinned GitHub-hosted runner image (the `ubuntu-latest` move that starts 2026-10-19), so it is a real, stable label rather than a moving `-latest` alias.

## Existing Tool Considered

- `ubuntu-26.04` is GitHub's own pinned runner label; no third-party tool covers this, so the change names the label directly in the workflows. It adds no code, no dependency and no new tool, and deletes no internal code.
