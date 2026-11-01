# Design

## Architecture

The hermetic floor prevents tests from modifying workspace files outside their allocated temporary directories.
A dedicated write guard module (`tests/support/spend_write_guard.py`) intercepts Python audit events for file modifications and SQLite database connections.

### 1. Spend Write Guard (`tests/support/spend_write_guard.py`)

- Registers an audit hook through `sys.addaudithook`.
- Monitors audit events: `open`, `os.rename`, `os.replace`, `os.remove`, `os.unlink`, and `sqlite3.connect`.
- Checks if the targeted file path matches `spend.db` or its related SQLite auxiliary files (`spend.db-wal`, `spend.db-shm`, `spend.db-journal`).
- Determines whether the path is outside the active pytest run temporary directory via `_outside_the_run`.
- Fails the test immediately using `pytest.fail` and records the violation in an internal list to enforce teardown failure even when swallowed by `except Exception:`.
- Automatically registered by `tests/support/bootstrap.py` as a pytest plugin.

### 2. Hermetic Floor Invariant Test (`tests/invariants/test_hermetic_floor.py`)

- Implements `test_a_spend_ledger_write_outside_the_run_fails_at_the_write_naming_the_test`.
- Uses `_run_with_floor` to execute an isolated test suite inside `pytester`.
- Verifies that:
  - An attempt to initialize `SpendLedger` targeting an outside path fails immediately, naming the test.
  - An attempt to write directly to an outside `spend.db` file fails immediately.
  - A caught exception still fails the test during teardown.
  - A spend ledger write targeting `tmp_path` succeeds cleanly.

### 3. Model Tests Isolation

- Tests calling `demo-model`, `fake-model`, or `test` ensure their spend records are written to a temporary spend ledger:
  - `tests/ai/client/test_ai_client_finish_reasons.py`: Add `spend_ledger` fixture.
  - `tests/ai/client/test_ai_client_retries.py`: Add `spend_ledger` fixture.
  - `tests/ai/client/test_ai_client_structured.py`: Add autouse `spend_ledger` fixture.
  - `tests/ai/client/test_response_cache.py`: Add autouse `spend_ledger` fixture.
  - `tests/ai/test_ai_client_style_request.py`: Add autouse `spend_ledger` fixture.
