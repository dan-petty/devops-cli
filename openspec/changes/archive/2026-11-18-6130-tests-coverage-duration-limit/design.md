# Design

## Decisions
- **Add a fifth test shard**: The test suite grew by 145 modules and more than 980 seconds of total test duration. Increasing the matrix in `.github/workflows/ci.yml` from `[1, 2, 3, 4]` to `[1, 2, 3, 4, 5]` reduces the recorded seconds per shard from 845.5 seconds to 676.4 seconds, bringing the shard wall clock duration from ~368 seconds to ~280 seconds in CI.
- **Refresh `tests/module_durations.json`**: Use `devops ci durations` to refresh module durations from the last 20 CI runs, ensuring new test modules are properly weighted and shards remain balanced.
- **Set `skip_specs: true`**: The change alters no user-facing CLI behavior, commands, or specs.

## Rejected alternatives
- **Raise the 360-second limit**: Rejected. AGENTS.md rule 5 and issue #6130 forbid raising the threshold.
- **Revert recent test additions**: Rejected. Tests verify active features and bug fixes across the repository.
- **Keep four shards**: Rejected. Even with perfect shard balance, four shards average 845.5 seconds of test execution, which causes the slowest shard plus coverage join to exceed 360 seconds.
