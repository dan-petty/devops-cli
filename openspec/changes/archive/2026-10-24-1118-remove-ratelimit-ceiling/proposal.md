# Proposal

## Why

The `ratelimit` library is abandoned upstream (#1118).
Its fixed window of 60 calls per 60 seconds causes silent stalls for up to one minute.
The library does not provide type information and ships only as a source distribution.
Existing rate limiter logic in `GitHubRateLimiter` already paces requests using quota reset timing and backoff.

## What Changes

- Remove the `ratelimit` dependency from `pyproject.toml` and lockfile manifests.
- Remove `_burst_protected_subprocess` and the 60-call fixed ceiling from `src/devops_cli/github/rate_limiter.py`.
- Call `run_subprocess` directly for gh command execution without `cast`.
- Remove `type: ignore` comments related to `ratelimit`.
- Update test cases that patched `_burst_protected_subprocess` to patch `run_subprocess`.
- Remove clock contract tests for the `ratelimit` window and update clock seam documentation.
- Add tests to verify no minute-long stall occurs on 61 calls and that parallel calls stay spaced.
- Update documentation and help text to replace token-bucket phrasing with quota-derived spacing.
- This change alters no behavior that an external consumer observes. The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/github/rate_limiter.py`, `src/devops_cli/core/clock.py`, `src/devops_cli/commands/gh.py`, `src/devops_cli/lang/en/help.py`, `pyproject.toml`, `uv.lock`.
- Tests: `tests/test_github_rate_limiter.py`, `tests/core/test_clock_contract.py`, `tests/support/fakes/clock.py`, `tests/support/fakes/github.py`, and test suites patching `_burst_protected_subprocess`.
- Documents: `README.md`, `docs/commands/gh.md`, `docs/CLI_REFERENCE.md`, `docs/SELF_IMPROVEMENT.md`.

## Feasibility

- Verified that `ratelimit==2.2.1` has had no release since 2018-12-17.
- Verified that `_execute_gh_single_attempt` delegates to `limiter._run_burst_protected`, which wraps `_burst_protected_subprocess`.
- Verified that `run_subprocess` returns `CompletedProcess[str]` directly and requires no `cast`.
- Verified that `GitHubRateLimiter.acquire` spaces requests across threads using quota state and minimum mutation intervals.
- Verified that `devops docs generate --sync-readme` updates documentation after modifying help text.

## Existing Tool Considered

Standard library `subprocess` and DevOps CLI `run_subprocess` provide subprocess execution without third-party wrapper overhead.
`GitHubRateLimiter` provides native quota pacing and backoff following GitHub API guidelines.
No additional third-party rate limiting library is required.
