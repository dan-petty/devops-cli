# Task: aiohttp 3.14.5 Clears Three Advisories, and the Maintain Test Runs No Real Audit (#1697)

**Issue**: [#1697](https://github.com/dan-petty/devops-cli/issues/1697)
**Scope**: scope/ci, scope/security
**Feasibility**: At release/v0.2.37 1eec7a1, `uv audit` reported GHSA-494j-54xm-rwp3, GHSA-5wr8-gcqf-gqf3 and GHSA-2g87-pp6c-29x5 against aiohttp 3.14.3, each fixed in 3.14.4, and `tests/test_ci_maintain.py::test_ci_maintain_live` failed on them, because `maintain` runs the audit through `_returncode(get_check_spec("audit").cmd)` (`src/devops_cli/commands/ci.py:1843`) and the test patched only `_run`. `uv lock --upgrade-package aiohttp==3.14.4` and the unpinned upgrade both move yarl from 1.24.5 to 1.25.1: aiohttp 3.14.5 declares `yarl<2.0,>=1.25.1`. With aiohttp 3.14.5, `uv audit` finds no known vulnerability in 223 packages.

## Description

- **The lock.** aiohttp moves to 3.14.5, the latest 3.14 patch, which carries the 3.14.4 fixes; yarl moves to 1.25.1 because aiohttp requires it. No other package moves.
- **The test.** `test_ci_maintain_live` patches `_returncode` too and asserts that `maintain` ran exactly the audit check's command, so it never starts a real `uv audit` and no advisory published later can fail it. What the audit's exit codes mean stays covered offline by `test_maintain_audits_with_uv_audit_and_says_whether_the_audit_ran`.

## Acceptance Criteria

- [x] `uv audit` at the branch reports no known vulnerability, and `uv lock --check` passes.
- [x] `test_ci_maintain_live` failed at 1eec7a1 on the three advisories, from a real `uv audit`, and passes at the branch with `_returncode` patched, asserting it ran only the audit check's command.
- [x] `uv run devops ci` passes (pre-push hook).

## Deliverables

- [x] `uv.lock`: aiohttp 3.14.5 and yarl 1.25.1.
- [x] `tests/test_ci_maintain.py`: `test_ci_maintain_live` runs no real audit.
- [x] `changelog.d/1697.md` and this task file.
