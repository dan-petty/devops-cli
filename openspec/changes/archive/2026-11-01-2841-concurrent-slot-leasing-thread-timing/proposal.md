# Proposal

## Why

Issue #2841 reports intermittent failures in `test_concurrent_slot_leasing_across_threads`.
The test verifies multi-threaded slot leasing across candidate nodes.
Under CPU load, worker thread ordering varies and fixed deadlines can expire.
The test must synchronize the first three acquired slots deterministically.
It must hold each candidate node until all three nodes are leased simultaneously.
It must use `THREAD_HANDOFF_BOUND_SECONDS` from `tests.support.waits`.

## What Changes

Update `test_concurrent_slot_leasing_across_threads` in `tests/ai/client/test_ollama_dynamic_leasing.py`:
- Use `threading.Barrier(3)` with a synchronized counter to hold the first three acquired slots simultaneously.
- Replace hardcoded 3.0 s timeouts with `THREAD_HANDOFF_BOUND_SECONDS`.
- Guarantee that all candidate nodes are leased regardless of thread scheduling order.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `tests/ai/client/test_ollama_dynamic_leasing.py`: Concurrent slot leasing becomes fully deterministic and passes repeatedly under load.

## Feasibility

- The test uses standard library synchronization primitives (`threading.Barrier` and `threading.Lock`).
- `THREAD_HANDOFF_BOUND_SECONDS` is imported from `tests.support.waits`.
- The product implementation in `devops_cli.ai.client.network` remains unchanged.

## Existing Tool Considered

`threading.Barrier` from the Python standard library covers the synchronization need.
No external tool is required.
