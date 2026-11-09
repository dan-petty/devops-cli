# Design

## Decisions

- **Use edge doubles instead of internal symbol patches**: Replace string patches of `devops_cli.*` with hermetic fakes (`ProcessFake`, `GitHubApiFake`, `ModelFake`, `ScannerFake`, `WebFake`, and `config`).
- **Support BaseException in ModelFake**: Allow test cases to simulate interruptions (such as `KeyboardInterrupt`) by checking `isinstance(candidate, BaseException)` in `_materialize_answer`.
- **Add isolate_env to ProcessCall**: Record `isolate_env` in `ProcessCall` within `ProcessFake` to allow telemetry tests to verify process isolation without mocking `run_subprocess`.
- **Include tests/commands in invariant check**: Add `"tests/commands"` to `_PATCH_FREE_COMMAND_TEST_DIRECTORIES` in `tests/invariants/test_source_tree.py` to prevent regression.

## Rejected alternatives

- **Retain ratchet ceilings**: Rejected because the goal is zero internal patches so issue #1336 can convert the ratchet into a ban.
- **Patch third-party packages instead**: Rejected because edge doubles provide reliable behavioral testing without monkeypatching.
