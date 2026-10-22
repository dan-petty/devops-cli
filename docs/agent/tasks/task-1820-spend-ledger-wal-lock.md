# Task: Opening the Spend Ledger From Several Threads at Once Succeeds (#1820)

**Issue**: [#1820](https://github.com/dan-petty/devops-cli/issues/1820)
**Scope**: scope/ai
**Feasibility**: Reproduced offline. Five threads released together on a barrier, each constructing `SpendLedger` on the same new path, raised `sqlite3.OperationalError: database is locked` in 13 of 300 trials and 27 of 300 on a second run, and in 6 of 40 with the tuned test shape, always at `PRAGMA journal_mode=WAL` in `_get_connection` (`ledger.py`), whatever the connection's 10 second timeout. SQLite returns `SQLITE_BUSY` at once for the switch to WAL. Remote CI showed it as `tests/test_ai_client_security.py::test_ollama_max_parallel_concurrency_slots` failing with `AIClientError: OperationalError: database is locked`, where five parallel `chat` calls each record their spend. With the change the same script ran 300 trials with no error.

## Description
WAL is a property of the database file, so it needs switching on once, but every connection executed `PRAGMA journal_mode=WAL`, and threads of one process did so at the same moment. `_get_connection` now reads the journal mode first and switches it only when it is not `wal`, with the read and the switch under one module-level lock, so the threads of a process never convert at once.

Two processes that convert the same new file at the same moment can still race, as before; this change does not claim to remove that.

## Key Changes
- `src/devops_cli/ai/spend/ledger.py`: `_JOURNAL_MODE_LOCK`, and the read-then-switch in `SpendLedger._get_connection`.
- `tests/test_ai_spend_ledger.py`: `test_a_new_ledger_opens_from_several_threads_at_once` opens forty new ledgers from five threads each.

## Acceptance Criteria
- [x] Five threads opening the same new ledger together raise no `OperationalError` (`test_a_new_ledger_opens_from_several_threads_at_once`; it fails at the base).
