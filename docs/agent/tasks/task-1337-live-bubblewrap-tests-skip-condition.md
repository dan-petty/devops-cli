# Task: Live bubblewrap tests skip condition (#1337)

**Issue**: [#1337](https://github.com/dan-petty/devops-cli/issues/1337)
**Status**: Done
**Milestone**: v0.2.29
**Priority**: priority/p1-high
**Scope**: type/bug, scope/security, scope/ci, priority/p1-high

## Description

The collection hook in `tests/conftest.py` previously evaluated `if True:` when checking whether bubblewrap was available on the host, inadvertently skipping every `bwrap`-marked test (21 tests, 22 cases) on all environments, including the devcontainer where `bwrap` 0.13.0 is installed.

The hook is updated to check `HostSandbox().is_available()`, adding the skip marker only where bubblewrap is not installed on the host. In environments where bubblewrap is available, all 22 live bubblewrap test cases execute and pass.

A regression test is added in `tests/test_host_sandbox.py` comparing the collected `bwrap`-marked items with the expected skip state according to `HostSandbox().is_available()`.

## Acceptance Criteria

- [x] The hook adds the bubblewrap skip to `bwrap`-marked tests only where `HostSandbox().is_available()` is false. It builds `HostSandbox` once per collection, not once per item, and never runs bwrap while collecting.
- [x] A regression test, not itself marked `bwrap`, compares the list of `bwrap`-marked tests that carry the bubblewrap skip with the expected list. Where `HostSandbox().is_available()` is false, every one of them carries it; where it is true, none does.
- [x] In the devcontainer, `uv run pytest -m bwrap -rs -p no:cacheprovider` reports 22 passed and nothing skipped: the 21 marked tests, with `tests/test_executable_criteria.py:615` counted twice.
- [x] On the PR's own GitHub CI run, Tests & Coverage passes and the regression test passes there, showing that the 22 cases skip on a runner without bwrap.
- [x] No test loses its `bwrap` marker, and `src/devops_cli/sandbox/` is unchanged.
- [x] `changelog.d/1337.md` records the change; `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes.
