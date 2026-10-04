# Task: CI Installs Nothing on the Runner, and Live Bubblewrap Tests Skip Where Bwrap Is Missing (#832)

**Issue**: [#832](https://github.com/dan-petty/devops-cli/issues/832)
**Status**: Done
**Milestone**: v0.2.26
**Priority**: priority/p1-high
**Scope**: type/refactor, type/infra, scope/github

## Description
Remove runner mutation steps (`sudo apt-get update`, `bubblewrap`, `python-is-python3`, and AppArmor unprivileged namespace relaxation) from `.github/workflows/ci.yml`. Register a `bwrap` pytest marker in `pyproject.toml` and implement a collection hook in `tests/conftest.py` that dynamically skips bubblewrap-dependent live tests with descriptive skip feedback when `bubblewrap` is not installed on the host. Make the namespace refusal test hermetic using an executable stub binary, and add an architectural invariant test ensuring that GitHub Actions workflows never mutate the runner and that `.devcontainer/Dockerfile` installs bubblewrap.

## Acceptance Criteria
- [x] No workflow changes the runner. `grep -rnE 'apt-get|sudo|sysctl' .github/workflows` prints nothing, and the invariant test in `tests/test_architectural_invariants.py` passes.
- [x] The invariant test fails if a `sudo apt-get install` step is added to `ci.yml`, and fails if `bubblewrap` is removed from `.devcontainer/Dockerfile`. Verified locally by testing each failure case, observing test failures, and reverting.
- [x] `bwrap` is a registered marker: `uv run pytest --markers` lists it with a description that names bubblewrap.
- [x] Where bwrap is missing, the marked tests skip and nothing fails. Verified by testing skip behavior with `pytest -m bwrap -rs` and verifying 0 failures and descriptive skip reasons.
- [x] `test_host_sandbox_handles_namespace_refusal` passes hermetically without requiring host bubblewrap by providing an executable stub binary under `tmp_path`.
- [x] In the devcontainer, `uv run pytest -m bwrap -rs` runs all marked tests with 0 skipped and 0 failed.
- [x] `uv run actionlint` passes on the edited `ci.yml`, and existing `tests/test_ci.py` workflow tests pass.
- [x] `src/devops_cli/sandbox/` is unchanged (`git diff --stat <base>..HEAD -- src/devops_cli/sandbox/` prints nothing).
- [x] Changelog fragment `changelog.d/832.md` and task file `docs/agent/tasks/task-832-ci-installs-nothing-live-bubblewrap-tests-skip.md` created without modifying `CHANGELOG.md` or `docs/ROADMAP.md`.

## Deliverables
- [x] `.github/workflows/ci.yml`: Deleted runner bubblewrap installation and sysctl steps.
- [x] `pyproject.toml`: Registered `bwrap` marker in `[tool.pytest.ini_options]`.
- [x] `tests/conftest.py`: Added `pytest_collection_modifyitems` hook to skip `bwrap` tests when bubblewrap is unavailable.
- [x] `tests/test_host_sandbox.py`: Marked live tests with `@pytest.mark.bwrap` and made namespace refusal test hermetic with a stub binary.
- [x] `tests/test_executable_criteria.py`: Marked live criteria tests with `@pytest.mark.bwrap`.
- [x] `tests/test_verdict_writers.py`: Marked `test_criteria_execution_verdict_finality` with `@pytest.mark.bwrap`.
- [x] `tests/test_architectural_invariants.py`: Added invariant test enforcing zero runner mutations across all workflows and ensuring bubblewrap is present in `.devcontainer/Dockerfile`.
- [x] `changelog.d/832.md`: Added changelog fragment under `### Changed`.
