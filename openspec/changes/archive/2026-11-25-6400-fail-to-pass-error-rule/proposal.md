# Proposal: #6400

## Why
Finish the three open items left by `#6379` for `devops ci fail-to-pass`:
- `CONTRIBUTING.md` still states that an unchanged test is repaired only when it fails on the plain merge base, while the code and `ci-fail-to-pass` spec already accept a failure or an error.
- `_repaired_and_refused` looks up only exact `test_id` matches on the head report, so an unchanged test file with a file-level collection error on base is always refused even when every test in that file passes on head.
- The error phase (`collection`, `setup`, `teardown`) is parsed from pytest's JUnit message prefix without a real-pytest test to catch an upstream pytest format change.

## What Changes
- Update `CONTRIBUTING.md` (`Fail-to-Pass Evidence`) so it states that an unchanged test is repaired when it fails or errors on the plain merge base and that a file-level collection error is repaired when the head report holds at least one case for that file and every head case passes.
- Add `TestCaseOutcome.error_phase` and update `_repaired_and_refused` in `src/devops_cli/ci/fail_to_pass.py` to accept a file-level collection error on the plain merge base as repaired when the head report holds at least one case for that module and all head cases of that module pass, while refusing it when any head case fails/errors or none exist.
- Add unit tests for repaired vs refused file-level collection errors and a `@pytest.mark.live("python")` test running real `pytest` on temporary modules with collection, setup, and teardown errors in `tests/ci/test_fail_to_pass.py`.

## Capabilities
- `ci-fail-to-pass`: Document the fail-or-error repair rule, accept repaired file-level collection errors across head module cases, and lock error phase parsing against real pytest JUnit output.

## Impact
- `CONTRIBUTING.md`
- `src/devops_cli/ci/fail_to_pass.py`
- `tests/ci/test_fail_to_pass.py`

## Feasibility
Confirmed against `origin/main`:
- `CONTRIBUTING.md:187` states "An unchanged test is repaired only when it fails on the plain merge base and passes on the head."
- `src/devops_cli/ci/fail_to_pass.py:1007-1030` (`_repaired_and_refused`) checks only exact `head_map.get(test_id)`, which misses module-path collection error IDs (`tests.test_mod` when head emits `tests.test_mod::test_foo`).
- `tests/ci/test_fail_to_pass.py` has only synthetic XML strings (`JUNIT_TEST_MOD_COLLECTION_ERROR`, `SETUP_ERROR`, `TEARDOWN_ERROR`) for error phase checks.

## Existing Tool Considered
The alternatives check on `#6400` returned `none` on 2026-11-19 and found no maintained library that exposes pytest collection/setup/teardown phases without keeping the repository's stdlib parser. Estimated cost to build and maintain: about 1,500 tokens and under half a day.
