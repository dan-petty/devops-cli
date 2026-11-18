# Design

## Decisions

- **Static ban via ruff TID251 banned-api**: Ruff TID251 refuses imports and direct attributes of `time.sleep`. Per-file ignores are forbidden by project invariants (`tests/gate/ruff_config.py`). Therefore, the clock seam module `src/devops_cli/core/clock.py` holds the single waiver under `# noqa: TID251` with the ceiling explicitly recorded at 1.
- **Audit hook in tests/conftest.py**: A session-scoped audit hook records `time.sleep` calls through `sys.addaudithook`. An autouse fixture measures sleep duration per test and fails tests exceeding 0.25 s unless marked with `real_sleep`.
- **Clock fixture compatibility**: `ClockFake` intercepts `time.sleep` with `fake.sleep`, avoiding standard library `time.sleep` audit events completely.
- **Real process waits keep real_sleep marker**: Tests that poll external child processes with `wait_while_running` declare `@pytest.mark.real_sleep`.

## Rejected Alternatives

- *Adopt pytest-fail-slow*: Measures total test duration rather than sleep duration. Fails slow tests that do not sleep and permits short sleeps in fast tests.
- *Ast-grep rule for sleep*: Cannot resolve aliased imports or allowlist single modules cleanly without rule-level ignores.
- *Monkeypatch time.sleep globally*: Misses calls bound at import time by third-party or sub-packages.
