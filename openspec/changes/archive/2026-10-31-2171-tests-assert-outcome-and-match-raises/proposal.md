# Proposal

## Why

Issue #2171: Some tests do not assert their claimed outcome, passing if no unhandled exception is raised. In addition, 39 `pytest.raises` call sites catch built-in exceptions (`KeyError`, `AttributeError`, `RuntimeError`, `SystemExit`) without `match=` or an exit-code check. A test that raises the wrong exception or fails for an unexpected reason still passes. The test suite must ensure each test asserts its outcome, built-in exception checks specify the expected failure message or exit code, and linting rules prevent new regressions.

## What Changes

- Add assertions to the no-assertion tests:
  - `tests/commands/test_argo.py`: assert `_validate_k8s_name` return values.
  - `tests/http/test_http_connection_pool.py`: assert idempotency and pool state on closing empty registry.
  - `tests/k8s/test_k8s_security_stream.py`: assert empty alerts rendering output via console capture.
  - `tests/ai/test_output.py`: assert fallback panel output via console capture.
  - `tests/ai/review/test_review_runner.py`: assert rendering output via console capture.
  - `tests/commands/test_vault_cmd.py`: assert validation of valid vault path.
- Update `pytest.raises` sites catching built-in exceptions (`KeyError`, `AttributeError`, `RuntimeError`, `SystemExit`) to include `match=` or verify `exc.value.code`.
- Configure Ruff `[tool.ruff.lint.flake8-pytest-style]` with `raises-require-match-for` for built-in exceptions.
- Add an `ast-grep` rule in `.ast-grep/rules/test-function-has-assertion.yml` and test in `.ast-grep/rule-tests/test-function-has-assertion-test.yml` to flag test functions without assertions.
- Set `skip_specs: true` in `.openspec.yaml`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Test files and lint configuration in `pyproject.toml` and `.ast-grep/rules/`.
- No production source files under `src/` are changed.

## Feasibility

- Running `ruff check --select PT011` enforces `raises-require-match-for`.
- Running `ast-grep scan` detects test functions without assertions or exception checks.
- Verification confirms that tests fail when tested behaviors are altered.

## Existing Tool Considered

Ruff `PT011` rule and `ast-grep`. No custom validation scripts are built.
