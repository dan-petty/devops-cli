# Proposal

## Why

Issue #2177: Many tests of error paths check only the exception type with `pytest.raises`. They verify no machine-readable error code, no process exit code, and no error message. A test passes when the system raises the expected exception class for an incorrect reason. Each test must assert the specific error code, the process exit code, or the error message. A static check must reject new bare `pytest.raises` sites.

## What Changes

- Update each bare `pytest.raises` site in `tests/` to verify the error code, the process exit code, or the error message:
  - For `DevOpsCLIError` subclasses, bind the exception or verify `match=` or `error_code`.
  - For `typer.Exit`, bind the exception and assert the exit code.
  - For library errors, pass `match=` with the expected message regex.
- Add an ast-grep rule `.ast-grep/rules/test-pytest-raises-checks-error.yml` that flags `pytest.raises` calls without `match=` or an `as` target.
- Add a test for the ast-grep rule in `.ast-grep/rule-tests/test-pytest-raises-checks-error-test.yml`.
- Register the new rule in architectural invariant suites (`CONST_TEST_CONSTRUCT_RULES` and construct rules tests).
- Set `skip_specs: true` in `.openspec.yaml`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Test files under `tests/`.
- Linter and construct rules under `.ast-grep/rules/`.
- No production source files under `src/` are changed.

## Feasibility

- The AST audit found 283 bare `pytest.raises` call sites in 118 test files.
- Each site can bind the raised exception to assert its attributes or supply a specific `match=` argument.
- Running `ast-grep scan` verifies that zero bare `pytest.raises` sites remain.

## Existing Tool Considered

`ast-grep` and `pytest`. No custom test runner is built.
