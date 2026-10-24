# Design

## Context

See `proposal.md` - Why.
`run_gh` passes gh commands through an in-memory burst ceiling using `ratelimit`.
The `ratelimit` package is abandoned and introduces unbounded blocking up to 60 seconds on the 61st call.
GitHub API pacing is already handled by `GitHubRateLimiter.acquire`, which enforces quota calculations and mutation intervals.

## Goals / Non-Goals

**Goals:**
- Eliminate the abandoned `ratelimit` dependency from the project.
- Execute gh commands directly with `run_subprocess`.
- Ensure gh calls do not stall for up to a minute when exceeding 60 requests.
- Preserve inter-thread spacing across parallel callers.
- Ensure all tests pass with zero imports of `ratelimit`.

**Non-Goals:**
- Implement a new cross-process burst ceiling library.
- Change the calculation formula for `GitHubRateLimiter.acquire`.
- Modify GraphQL mutation classification beyond existing implementations.

## Decisions

### Decision 1: Remove ratelimit and Execute via run_subprocess

`_execute_gh_single_attempt` will call `run_subprocess` directly instead of `limiter._run_burst_protected`.
The helper function `_burst_protected_subprocess` and the attribute `_run_burst_protected` will be removed.
`run_subprocess` returns `subprocess.CompletedProcess[str]`, removing the need for `typing.cast`.

*Alternatives considered:*
- Replacing `ratelimit` with another third-party library: rejected because GitHub API limits are already managed by `GitHubRateLimiter`.

### Decision 2: Remove Clock Contract Tests for ratelimit

`tests/core/test_clock_contract.py` tested the monotonic clock seam using `ratelimit.limits`.
These tests and the `ratelimit` imports will be removed.
The clock seam contract will test monotonic time advancement directly.

*Alternatives considered:*
- Keeping `ratelimit` in the dev dependencies solely for tests: rejected because `ratelimit` is unmaintained and should be completely removed.

### Decision 3: Update Test doubles to Patch run_subprocess

Existing tests that mocked `_burst_protected_subprocess` will mock `devops_cli.github.rate_limiter.run_subprocess` instead.
This aligns test seams with standard process execution.

*Alternatives considered:*
- Keeping an internal alias `_burst_protected_subprocess`: rejected because no shims or backward-compatibility wrappers are kept in alpha versions.
