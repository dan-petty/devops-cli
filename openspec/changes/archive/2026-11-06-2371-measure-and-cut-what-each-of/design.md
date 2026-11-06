# Design

## Decisions

- **Pass file paths to pytest.**: Pytest collects only the files it gets. No worker imports a test module of another shard, and no plugin is needed.
- **Deal by lines of test code, heaviest file first.**: Each module goes to the shard with the fewest lines so far. A tie goes to the lower shard number. The split reads only the tree, so each runner computes the same lists from the same checkout, and no stored file can go out of date. A new test module joins a shard with no other step.
- **Reuse `_directory_modules("tests", root)`.**: It gives the same 830 files that pytest collects, and it is the function that `devops ci test` already uses to expand a directory.
- **Keep the coverage options.**: A shard keeps `--cov=src`, `--cov-report=`, `--cov-fail-under=0` and `--snapshot-warn-unused`. The snapshots of the other shards are unused in a shard.
- **Remove `pytest-split`.**: Nothing else uses it.
- **The unsharded row is unchanged.**: With `--shards` at 1 the row passes no path, and pytest takes `testpaths` as before.

## Balance

At 4a2d958e the split by lines gave 4,834, 5,181, 4,971 and 4,528 tests per shard. The largest is 6.2% above the mean. A split by file size gave 14.4%, so it is not used. A split by test count is exact but needs a collection or a stored file. The old split dealt single tests, so its shards were equal in count. If the shard times spread too far after this change, a follow-up item can add a stored per-file duration file. That is out of scope here.

## Rejected alternatives

- **A preload fixture for heavy modules, and fewer workers.**: Worker start is 2.8% of the CPU and a preload fixture gives 0%. Fewer workers raise the wall time (issue comment of 2026-11-05).
- **`pytest-test-groups`, `pytest-shard`, `--dist loadfile`, a `pytest_ignore_collect` plugin.**: See "Existing Tool Considered" in `proposal.md`.
- **A split by file size.**: 14.4% imbalance, against 6.2% for lines.
- **A stored duration file.**: It can go out of date, and the balance by lines is enough for now.
