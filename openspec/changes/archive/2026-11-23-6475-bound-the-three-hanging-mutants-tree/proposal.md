# Proposal: #6475

## Why

Three tests do not end in 70 minutes in a mutants tree of all of `src/devops_cli`.
They read the 475 MB generated tree.
This change adds size and duration bounds to prevent test hangs.

## What Changes

- Add `PARSED_TREE_BOUND_BYTES` (128 MiB) and `ROUND_LOOP_BOUND_SECONDS` (60.0s) constants in `tests/support/waits.py`.
- Add `tree_guard` in `tests/support/trees.py` to skip tests when parsed source exceeds 128 MiB.
- Update `tests/telemetry/test_telemetry_instruments.py` to call `tree_guard` before gauge validation.
- Update `tests/invariants/test_source_tree.py` to call `tree_guard` before checking unreachable calls.
- Update `tests/server/test_service_memory.py` to check elapsed round time and skip after 60 seconds.

## Capabilities

### Modified
- `ci-test-selection`: The test harness bounds source tree size and test duration in generated mutant trees.

## Impact

The three slow tests end promptly or skip on large generated mutation trees.
Normal test runs remain unchanged.

## Feasibility

Verified against the mutants tree issue description and test support codebase.
The limits stop test hangs before traversal.

## Existing Tool Considered

`pytest-timeout` bounds test duration but fails expired tests without a custom skip reason.
Repository test support bounds skip with a reason that names the generated tree.
The cost to build is 40 lines of test support code.
