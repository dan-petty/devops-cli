# Proposal

## Why

The Tests & Coverage required CI check averages over 7 minutes, exceeding the 5-minute bound in AGENTS.md rule 5. The regression from 4 minutes 42 seconds to 7 minutes is traced to interpreter startup cost, per-worker repetition, and coverage measurement overhead. See #3050.

## What Changes

- Enable uv cache and parallel worker execution in the Tests & Coverage job to reduce wall-clock time
- Extend the Test Job Duration window from 10 to 20 runs to match the acceptance criterion
- Record step times of a slow run and a fast run in issue #3050, naming the difference
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-job-time`: duration-window-size

## Impact

- Code: `.github/workflows/ci.yml`

## Feasibility

- The premise is confirmed by the measured times in the issue body. Six runs on 2026-10-31 and 2026-11-01 show times from 5 min 59 s to 7 min 21 s.
- AGENTS.md rule 5 states: 'A build or check that averages more than 5 minutes is a P0 bug.'
- The Test Job Duration job already exists in `.github/workflows/ci.yml` and enforces the 300-second bound over 10 runs.
- The first check the implementation runs is `actionlint .github/workflows/ci.yml` to validate the modified workflow.
- The second check is `uv run devops ci --check --no-cache --only test` to measure the local test duration after the change.

## Existing Tool Considered

The project already uses pytest, coverage.py, and GitHub Actions. The change optimizes their configuration (caching, parallelism) rather than replacing them. No new tool is introduced.
