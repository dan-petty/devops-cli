# Tasks

## 1. Behavior: run time without the queue, and the schedule trigger

- [x] 1.1 Add the failing tests: a sharded run is its slowest shard plus the join, run 43018142394 gives 472 s and a queue time of 503 s, the limit does not count the queue time and the command prints it on its own line, the job runs on `schedule` and `workflow_dispatch` only, and the concurrency group of `ci.yml` holds the event
  - Verification: `$ uv run devops ci test tests/github/test_ci_job_time.py`
- [x] 1.2 Time a run by its slowest shard and the join in `GitHubClient._job_run_time`, add `queue_seconds` and its mean, print the queue line, and change the trigger and the concurrency group of `ci.yml`
  - Verification: `$ uv run devops ci test tests/github/test_ci_job_time.py tests/commands/test_ci.py`
- [x] 1.3 Check the workflow
  - Verification: `$ uv run devops ci --only actionlint,zizmor`

## 2. Documents

- [x] 2.1 State the new time of a run and the new triggers in `docs/TESTING.md` and in the help of `--job`, and regenerate the command reference
  - Verification: `$ uv run devops docs generate --check`
