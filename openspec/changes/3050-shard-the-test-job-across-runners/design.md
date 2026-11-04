# Design

## Decisions

- **Split the job into 4 shard jobs and one aggregate job named `Tests & Coverage`.**: The measure shows 355 s on the fastest recent runner and 528 s on a slow one for the same suite, so no cut of constant work reaches 300 s on both. Each shard runs a quarter of the tests, so the test time falls to about 80 s to 125 s. ADR 0004 names top-level aggregating jobs as the stable contract of the ruleset, so the required name stays on the aggregate.
- **Add `--shard` and `--shards` to `devops ci`, and change only the command of the `test` row.**: `build_subprocess_env` refuses `PYTEST_ADDOPTS` (#2747), so the workflow cannot pass the split options through the environment. The gate stays the one entry point of every workflow step, and `tests/commands/test_ci.py` already checks that rule. A run with `--shards` above 1 is narrowed: it reads and writes no cached verdict, because it proves a part of the suite.
- **Split with `pytest-split` and `--splitting-algorithm least_duration`, with no stored durations.**: With no durations, every test weighs the same, and `least_duration` deals the tests one after the other to the group with the least weight. The heavy tests of a directory spread over the shards. A stored `.test_durations` file would be a generated file of 18,000 entries that goes stale on each new test.
- **A shard sets `--cov-fail-under=0` and `--cov-report=`.**: A shard measures a quarter of the tests and would fail the floor of 85% alone. The report of a quarter says nothing, and printing 560 files costs time. The data file stays in `.data/.coverage`.
- **The aggregate job combines the data with `coverage combine` and checks the floor with `coverage report`.**: `fail_under` stays in `pyproject.toml` and holds for the combined data, as before the split. The step `Changed-Line Coverage` and its 90% floor do not change. The shards run on identical paths, so the combined data matches the checked-out source.
- **The aggregate runs when no job was cancelled, and fails when a shard did not succeed.**: A skipped job counts as success for a required check. With `!cancelled()` and an explicit failing step, a failed shard turns the required check red and does not skip it. The step comes before every other step, so a failed shard stops the download and the combine.
- **`devops ci job-time` measures from the first start of the jobs of the check to the end of the job of that name.**: The aggregate alone lasts about 70 s, and a mean of that would hide the time that a person waits. The measure is the wall time of the check. For runs without shard jobs it is the time of the one job, so the 20-run window reads old and new runs with one rule.
- **The window grows to 20 runs.**: The issue states the mean over 20 runs of `main`.
- **Shards are 4.**: The estimate gives about 215 s to 260 s. A fifth shard saves about 15 s to 25 s and adds a runner to a repository that runs about 10 jobs on each pull request, where the limit of concurrent jobs is 20. The list `matrix.shard` and the name of the job hold the count in one place (`strategy.job-total`), so raising it is a one-line change when `Test Job Duration` nears the bound.

## Rejected alternatives

- **Cut the constant work only: the 56 start-ups of #2369, the repeated collection of #2371, the coverage cost of #2373.**: The fast run of 355 s is already over the bound. #2369 closed because its premise is false (paired runs gave a ratio of 0.97 to 1.02). The other two items stay open and may lower the shard time later, but no figure in them brings the slow runners from 528 s to 300 s.
- **Run on a larger runner.**: The owner sets the runner type and its cost. The repository has no such setting, so the change cannot make it.
- **Select tests by the changed files (`pytest-testmon`, `devops ci test --changed`).**: ADR 0004 rejected mandatory test selection (#406): the full suite must run authoritatively on the merge gate.
- **Skip or merge slow tests.**: The owner rule of 2026-10-23 forbids skipping a check.
- **Pass the split options in `PYTEST_ADDOPTS`.**: The subprocess guard refuses the key (#2747), and the guard is a security control.
- **Make the shard jobs the required checks.**: ADR 0004 rejects binding the ruleset to matrix jobs, and a change of the matrix would break the ruleset.
- **Use `duration_based_chunks`.**: It cuts the ordered list into runs of equal size, so one directory with the heavy tests lands in one shard.
- **Measure the aggregate job alone in `job-time`.**: That would report about 70 s and hide the wait of a person. It would lower the measured time without lowering the time of the check.

## Risks

- The mean of 20 runs of `main` includes the single-job runs for about 15 pushes after the merge, so `Test Job Duration` can stay red for that time. The job is not a required check and no pull request waits for it.
- A test that depends on the tests before it in one process fails in a shard only. `Changed-Test Independence` and the module-independence invariant guard that.
- The cache of `.pytest_cache` is per shard, because a cache key written by four jobs at once would race.
