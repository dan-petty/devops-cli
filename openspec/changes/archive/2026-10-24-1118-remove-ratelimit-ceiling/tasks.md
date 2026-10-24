# Tasks

## 1. Specification and Behavioral Tests

- [x] 1.1 Add a unit test in `tests/test_github_rate_limiter.py` asserting that 61 calls do not stall for up to a minute, and verify initial failure before removing `ratelimit`.
- [x] 1.2 Add a unit test in `tests/test_github_rate_limiter.py` asserting that parallel callers stay spaced across threads using `threading.Barrier`.
- [x] 1.3 Add a unit test in `tests/test_github_rate_limiter.py` asserting that a non-exempt call without an endpoint still calls `acquire`.

## 2. Remove ratelimit and Internal Ceiling Wrapper

- [x] 2.1 Remove `ratelimit==2.2.1` from `pyproject.toml` and update `uv.lock`.
- [x] 2.2 Remove `_burst_protected_subprocess`, `_run_burst_protected`, and `ratelimit` imports from `src/devops_cli/github/rate_limiter.py`.
- [x] 2.3 Call `run_subprocess` directly in `_execute_gh_single_attempt` and remove unused `cast` import.

## 3. Update Test doubles and Test Suites

- [x] 3.1 Update all tests patching `_burst_protected_subprocess` to patch `run_subprocess`.
- [x] 3.2 Update `tests/core/test_clock_contract.py`, `tests/support/fakes/clock.py`, and `src/devops_cli/core/clock.py` to remove `ratelimit` references.
- [x] 3.3 Verify all tests in `tests/test_github_rate_limiter.py` and `tests/core/test_clock_contract.py` pass.

## 4. Documentation and Help String Updates

- [x] 4.1 Update help strings in `src/devops_cli/lang/en/help.py` and `src/devops_cli/commands/gh.py` to replace token-bucket phrasing with quota-derived spacing.
- [x] 4.2 Run `uv run devops docs generate --sync-readme` and verify `uv run devops docs check` passes.

## 5. Verification and Quality Gate

- [x] 5.1 Run `uv run devops ci fail-to-pass --base origin/main` to verify the failing test evidence.
- [x] 5.2 Run `uv run devops ci` to ensure all static checks and test suites pass.
- [x] 5.3 Archive OpenSpec change with `uv run devops openspec archive 1118-remove-ratelimit-ceiling`.
