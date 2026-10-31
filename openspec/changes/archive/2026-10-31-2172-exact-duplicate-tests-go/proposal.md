# Proposal

## Why

Issue #2172: An audit of the test suite found three exact duplicate tests across modules and multiple groups of near-duplicate tests that differ only in literal constants. Exact duplicate tests increase test execution time and maintenance burden. Near-duplicate tests duplicate assertion logic where a single parametrized test checks each case with its input constants.

## What Changes

- Delete the three exact duplicate tests:
  - Remove duplicate line-numbering tests from `tests/review/test_review_diff.py` and preserve them in `tests/review/test_review_page_line_numbers.py`.
  - Remove duplicate credential arrival test from `tests/server/routes/test_k8s_roadmap_service.py` and preserve the test in `tests/config/test_k8s_devops_runtime.py`.
- Parametrize near-duplicate test groups using `pytest.mark.parametrize` with descriptive test ids.
- Keep all test assertions and input constants intact across parametrized tests.
- Maintain total collected test count equal to the previous count minus the three deleted duplicate tests.
- Set `skip_specs: true` in `.openspec.yaml`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Test files under `tests/review/`, `tests/server/routes/`, `tests/commands/`, `tests/security/`, `tests/github/`, `tests/ai/`, `tests/dry_run/`.
- No production source files under `src/` are changed.

## Feasibility

- AST analysis confirmed three exact duplicate test bodies in the test suite.
- Verification checks for unique matches of `test_credentials_arrive_only_through`, `test_diff_lines_carry_their_new_file_numbers`, and `test_numbers_strip_back_to_the_original_text`.
- Running `pytest --collect-only -q` before and after verifies that exactly three duplicate test cases are removed.

## Existing Tool Considered

Pytest built-in `pytest.mark.parametrize` decorator. No custom parametrization runner is built.
