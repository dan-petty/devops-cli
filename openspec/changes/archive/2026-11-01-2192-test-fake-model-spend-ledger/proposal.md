# Proposal

## Why

Issue #2192 reports that fake model calls in tests wrote rows into the default spend ledger at `.data/ai/spend.db`.
The workstation spend ledger holds production spend records.
Tests must never write to `.data/ai/spend.db` outside the run temporary directory.
The hermetic floor must fail any test that opens or writes to the default spend ledger path outside the run temporary directory.
Tests that make fake model calls (`test`, `fake-model`, `demo-model`) must record them in a ledger under `tmp_path`.

## What Changes

- Add `tests/support/spend_write_guard.py` using a PEP 578 audit hook to refuse file and SQLite write access to `spend.db` outside the run temporary directory.
- Add an architectural invariant test in `tests/invariants/test_hermetic_floor.py` that fails when a test writes to the default spend ledger path outside the run temporary directory.
- Update tests that make `test`, `fake-model`, and `demo-model` calls to isolate their spend ledger under `tmp_path`.
- Document the spend ledger write guard in `docs/TESTING.md`.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `tests/support/spend_write_guard.py`: Refuses spend ledger writes outside the test run temporary directory.
- `tests/invariants/test_hermetic_floor.py`: Verifies that spend ledger writes outside the temporary directory fail the test.
- `tests/ai/client/test_ai_client_finish_reasons.py`, `tests/ai/client/test_ai_client_retries.py`, `tests/ai/client/test_ai_client_structured.py`, `tests/ai/client/test_response_cache.py`, `tests/ai/test_ai_client_style_request.py`: Use `spend_ledger` fixture to write records under `tmp_path`.
- `docs/TESTING.md`: Documents the spend ledger write guard in the hermetic floor specification.

## Feasibility

- The PEP 578 audit hook pattern is verified and already in active use by `tests/support/config_write_guard.py`.
- `sqlite3.connect` and file change events (`open`, `os.rename`, `os.remove`) emit standard Python audit events.
- The `spend_ledger` fixture in `tests/support/spend.py` already creates an isolated temporary database under `tmp_path`.

## Existing Tool Considered

Python PEP 578 audit hooks (`sys.addaudithook`) provide the standard mechanism for process security boundaries and write protection in the devops-cli test runner.
