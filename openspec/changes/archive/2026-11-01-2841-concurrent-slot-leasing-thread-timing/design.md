# Design

## Problem Statement

The test `test_concurrent_slot_leasing_across_threads` tests multi-threaded slot acquisition.
It uses three candidate nodes with `max_parallel=1`.
Under load, worker threads can finish and release slots before all three candidate nodes are leased.
In addition, the existing barrier wait and lease timeout use hardcoded 3.0 s deadlines.
This behavior violates `docs/TESTING.md`, which prohibits fixed deadlines for thread waits.

## Proposed Changes

1. In `tests/ai/client/test_ollama_dynamic_leasing.py`, import `THREAD_HANDOFF_BOUND_SECONDS` from `tests.support.waits`.
2. In `test_concurrent_slot_leasing_across_threads`, create a `threading.Barrier(3)` and a `threading.Lock`.
3. Track the count of workers that have acquired slots.
4. Have the first three workers that acquire slots wait at the barrier.
5. Because `max_parallel=1`, the first three workers must acquire three distinct nodes.
6. Holding all three workers at the barrier guarantees that all three nodes are leased simultaneously.
7. Use `THREAD_HANDOFF_BOUND_SECONDS` for both the lease timeout and the barrier wait.

## Acceptance Criteria Verification

1. `tests/ai/client/test_ollama_dynamic_leasing.py` contains no numeric timeout deadlines.
2. The test passes 50 consecutive runs under `uv run devops ci test tests/ai/client/test_ollama_dynamic_leasing.py --repeat 50`.
