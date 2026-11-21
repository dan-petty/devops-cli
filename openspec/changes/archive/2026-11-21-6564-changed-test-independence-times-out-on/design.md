# Design

## Decisions

- **Run each shuffled run on the xdist workers that a narrowed run gets.**: A run of the 1,473 tests of #6562 took 454 s on one process. `Tests & Coverage` runs about 5,000 tests in each shard in 139 s to 193 s on 4 workers. `_narrowed_workers` already chooses the workers of a narrowed run: one process for up to 50 collected tests, where the start of the workers costs more than it saves, else 4 workers. A one-file change thus stays on one process.
- **Choose the workers one time for all runs of a repeat.**: The collection is a second pytest session, and the runs select the same files with the same `-k` filter, so one count is true for each run.
- **Start each of the three runs on a runner of its own, with the new option `--run`.**: Each run already was a pytest session of its own with its own seed, so three jobs give the same three runs. The job time is then the time of one run, not of three. The option keeps the seed rule in the command: run `<k>` gets the seed `first + k - 1`, where `first` is `--seed` or the value from the commit hash of HEAD.
- **Keep the set of each run whole.**: Each run gets each changed test file, so a test can meet each other changed test in its process, as before. pytest-randomly keeps the tests of one module together in its order, and xdist with `--dist worksteal` gives each worker one part of that order, so most tests of one module run in one worker.
- **Give the check name `Changed-Test Independence` to an aggregate job.**: A person reads one check with one result, as with `Tests & Coverage` and its shards. The aggregate fails when the matrix result is not `success`, as the step `Require Passing Test Shards` does, because a skipped job would show as a pass.
- **Keep the job id `changed-tests` on the matrix job.**: The requirement `The test jobs skip the bytecode compile` of `ci-job-time` names that job, and the matrix job keeps `compile-bytecode: "false"`.
- **Give each run its own tooling cache key.**: Three jobs that save one key at the same time race, as the comment of `test-shard` says.
- **Give the test step a limit of 12 minutes under the job limit of 15 minutes.**: The limits nest: the 600 s bound of one test < 720 s of the step < 900 s of the job. A step that passes its limit fails with a message that names the step, so the job gives a result and is not cancelled.
- **Let `-n` apply to a repeat run.**: The help said that a repeat run ignored `-n`. A caller who gives `-n` now gets those workers, as in each other narrowed run.

## Rejected alternatives

- **Eight file shards, each with three serial runs (the first plan of this change).**: The split keeps each file in one process, and `test_roadmap_implement_job.py` records 191.8 s of the 988 s of the 53 files of #6562, so its shard runs it three times on one process. It also starts eight runners for each pull request that changes a test file, seven of them with no file for a one-file change. The first plan also said that xdist workers share one process; they are separate processes.
- **xdist workers in one job with the three runs one after another.**: One run of 1,473 tests on 4 workers takes about 454 s / 4 = 114 s at best, so three runs and the setup take more than 360 s.
- **A prepare job that computes the number of shards from the recorded seconds.**: It adds a job of about 30 s before each run of the check, and a new command output. The three runs cover each change of the last 21 days: the largest recorded 1,318 s, about 1.3 times the 988 s of #6562.
- **pytest-repeat with `--count 3`.**: It repeats each test in one session with one seed, so the three runs get no new shuffle and run in one process.
- **A higher job timeout.**: The issue forbids it, and the job gives no result before the cancel.
- **Pass the check when one run passes, or retry a failed run.**: Both hide a test that depends on the order, which the check exists to find.

## Unchanged references

- `openspec/specs/ci-job-time/spec.md` (spec): The job id `changed-tests` stays on the matrix job, which still passes `compile-bytecode: "false"` to `setup-toolchain`.
- `docs/adr/0012-releases-are-derived-by-release-please-from-trunk-and-milestones-are-planning-buckets.md` (document): It says that the `changed-tests` job finds nothing to do on the release pull request. The matrix job and the aggregate job keep the release skip.
- `tests/fixtures/github/ci_runs_main.json` and `tests/fixtures/github/check_runs_pr_5357_head.json` (fixtures): They record runs of past heads. A recorded run is not written again.
- `CHANGELOG.md` (document): Released history. release-please writes the next line from the pull request title.
