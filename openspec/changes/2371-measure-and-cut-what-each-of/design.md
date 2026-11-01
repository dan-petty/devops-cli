# Design

## Decisions

- **Use a session-scoped fixture in tests/conftest.py to pre-import heavy modules.**: This moves the import cost from individual tests to a known, one-time place per worker. It is the smallest change that removes the import overhead from test durations.
- **Target pydantic_ai, anthropic, kubernetes, and textual as the heavy modules.**: These are listed in CONST_CLI_HEAVY_MODULES in tests/test_cli_startup_imports.py:17 and are the modules the issue identifies as the heaviest first imports.
- **Use importlib.import_module instead of a bare import statement.**: A bare import at module level in conftest.py would run at collection time, not at session start. importlib.import_module inside the fixture body runs at session start, which is the intended timing.

## Rejected alternatives

- **Reduce the worker count to -n 3 or -n 2 on the 4-CPU runner.**: This reduces parallelism and increases wall time. The issue lists it as a candidate but the session fixture targets the root cause (repeated imports) without reducing parallelism.
- **Remove imports from the top of test modules to shorten collection.**: This is a large refactor across many test files. The session fixture achieves the same goal (removing import cost from tests) with a single change to conftest.py.
