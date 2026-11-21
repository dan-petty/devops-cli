# Design

## Decisions

- **Give `-n 0` in place of `-o addopts=`.** The empty `addopts` stopped the xdist workers of `-n logical`, and it also removed the other values of `addopts`. `-n 0` stops only the workers. pytest puts `addopts` before the command line, so the last `-n` wins.
- **Keep the replay in one process.** A replay runs few test files. An explicit `-n` count calls no `pytest_xdist_auto_num_workers`, so the replay takes no gate slot and does not wait for a `devops ci` run.
- **Give no `--no-cov`.** `addopts` holds no `--cov`, so coverage is off in the replay without it.

## Rejected alternatives

- **Change the test to read the configuration of the run.** The test checks the `addopts` of `pyproject.toml`, which is the configuration of the full gate. The replay, and not the test, changed that value. Another test that reads `addopts`, or that needs the plugins or the Hypothesis profile of `addopts`, would also fail.
- **Remove some values from the `addopts` string.** That repeats the parse of pytest, and it can remove a value that a test reads.
- **Keep `-n logical` in the replay.** The replay then takes a gate slot and starts a worker for each CPU, for a few test files.
