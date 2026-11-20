# Design

## Decisions

- **Run the changed test files in a matrix of eight shard jobs with one aggregate job.**: `openspec/specs/ci-test-shards/spec.md` records this pattern for long test work, and the job `test-shard` of the workflow already uses it for the suite.
- **Give the check name `Changed-Test Independence` to the aggregate job.**: A person reads one check with one result, as with `Tests & Coverage`, and the check is not required, so no ruleset reads the name.
- **Keep the job id `changed-tests` on the matrix job and give the aggregate the id `changed-tests-result`.**: The requirement `The test jobs skip the bytecode compile` of `ci-job-time` names the `changed-tests` job, and the matrix job keeps the toolchain step with `compile-bytecode: "false"`, so that requirement stays true.
- **Balance the changed files across eight shards by the recorded seconds of the duration record.**: The reported 454 s for one pass over 1,473 tests gives about 57 s per pass in a shard, about 170 s for three passes and about one minute of setup, under the 300 s bound; four shards leave no margin.
- **Fail the aggregate job when the matrix does not succeed.**: The step `Require Passing Test Shards` of the job `Tests & Coverage` does the same, and one red check names the failed shard.
- **Give the aggregate job the pull request condition, the release skip and `!cancelled()` in its `if`.**: The matrix job runs only on a pull request, so a push to `main` would otherwise run the aggregate and fail it on a skipped need; `!cancelled()` keeps it running after a failed shard, whose default `if` is `success()`.
- **Keep the job limit of the matrix at 15 minutes and give the test step 12 minutes.**: The issue forbids a higher timeout, and a step limit under the job limit fails a slow shard with a message that names the step; the invariant test compares a step limit with its own job limit, so 12 under 15 passes.
- **Exit 0 and start no pytest when a shard holds no file, and print no new message for it.**: `devops ci test` passes no target to pytest when its list is empty, and pytest would then collect the whole suite; seven of eight shards are empty for a pull request that changes one test file, and the step `Detect Changed Test Files` already prints the file list that a reader compares with the shard count.
- **Let a changed-file shard be empty, while the suite split keeps every shard non-empty.**: The base requirement `Each shard collects only its own test files` covers the split of the whole suite, whose modules fill every shard; a changed-file list can hold fewer files than the shards, so its own requirement states the empty-shard rule for that list alone.
- **Reuse the splitter, the refusal and the help texts of `devops ci` for a given list of test files.**: The recorded seconds already weigh the split of the suite, and `HELP.ci.shard`, `HELP.ci.shards` and `MESSAGES.ci.shard_above_total` stay true of a sharded test run, so a second wording would drift from them.
- **Read no cached verdict and write none in a sharded changed-test run.**: The base requirement `A sharded run reads and writes no cached verdict` of `ci-test-shards` requires it, and a shard's verdict is not the verdict of the whole changed set.
- **Give each shard job its own tooling cache key and let it list the changed test files itself.**: Eight jobs that save one key at the same time race, as the comment of `test-shard` says, and one git diff per job costs seconds and needs no artifact.
- **Update the workflow parity allowlist in the same group as the workflow change.**: The parity check refuses a run step that runs no gate row, so the aggregate step and its allowlist row are one change and the group never fixes a test that only breaks.
- **Verify the workflow group with the two test modules that pin the workflow.**: The parity test module reads the file and checks the allowlist, and the workflow contract test module checks each job limit and each step limit, so one command catches a broken edit before the group ends.
- **Add no `devops ci job-time` alarm for the changed-test check.**: The check runs only on a pull request, and `devops ci job-time` reads push runs of `main`, where the job is skipped.

## Rejected alternatives

- **Three jobs, one for each repeat pass.**: It gives a 3x gain only, so a larger changed set still reaches the limit, and it needs a new option for the pass seed.
- **Parallel workers of `pytest-xdist` in one job.**: It keeps one job and one time bound, and the workers share the state of one process, so the job still reaches its limit.
- **A higher job timeout.**: The issue forbids it, and the job still gives no result before the cancel.
- **Four shard jobs.**: The reported 454 s per pass gives about 341 s for three passes, which leaves no margin under the 300 s bound.
- **A matrix that a prepare job computes from the recorded seconds.**: It needs a prepare job and a new command output, and the fixed matrix meets the proof of the issue.
- **Each shard job holds the check name.**: A matrix makes the name of the check unstable in the checks list.
- **A new name for the check.**: It loses the history of the check, and no reason asks for it.
- **Pass the aggregate job when the first shard passes.**: It hides a failed shard and gives a wrong result.
- **Retry a failed shard once.**: A retry hides a flaky test that the check exists to find.
- **Reuse one cached verdict for each shard, or write one for each shard.**: `devops ci test` reads and writes no cached verdict at all, and a shard of a changed set is not stable between runs.
- **Split the changed file list in the workflow with a shell one-liner.**: The project keeps the gate as the one entry point of every workflow step, and the split needs the recorded seconds, which only the Python splitter reads.
- **Give the changed-tests test step a limit of 5 minutes.**: The reported 454 s of one pass over 1,473 tests gives about 170 s for three passes in a shard plus setup, so 5 minutes leaves too little margin for the slowest runner.

## Unchanged references

- `openspec/specs/ci-job-time/spec.md` (spec): The job id `changed-tests` stays on the matrix job, which still passes `compile-bytecode: "false"` to `setup-toolchain`.
- `docs/adr/0012-releases-are-derived-by-release-please-from-trunk-and-milestones-are-planning-buckets.md` (document): It says the `changed-tests` job finds nothing to do on the release pull request; the matrix job keeps its release skip.
- `tests/fixtures/github/ci_runs_main.json` (fixture): It records runs of past heads of `main`, where the job was skipped; a recorded run is not rewritten.
- `tests/fixtures/github/check_runs_pr_5357_head.json` (fixture): It records the check runs of one past head; a recorded run is not rewritten.
- `CHANGELOG.md` (document): Released history; release-please writes the next line from the pull request title.
