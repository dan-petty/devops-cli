# Design

## Decisions
- The step passes `-rfEs`, the same characters as the `devops ci` shard row (`CONST_CI_SHARD_SUMMARY_CHARS`). The test builds the expected option from that constant, so the two shard kinds cannot drift apart.
- The step keeps `-q` and `--durations=10`. Only the summary characters change.

## Rejected alternatives
- `-ra`: it adds the passed-with-output and xfail lines, which make the log longer and which the issue does not ask for.
- `-r` in `addopts` of `pyproject.toml`: each local run and each mutation run would then print the summary. Only the shards need it, and the `devops ci` row sets it on its own command line.
