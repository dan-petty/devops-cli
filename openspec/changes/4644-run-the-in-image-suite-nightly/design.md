# Design

## Decisions
- A workflow of its own with the native `on.pull_request.paths` filter. GitHub evaluates the filter before it starts a run, so a pull request that changes only `src/` or only a plan starts no job.
- The image inputs are the files that the build reads other than `src/`: `Dockerfile`, `.dockerignore`, `pyproject.toml`, `uv.lock` and `src/devops_cli/tools_lock/**`. The workflow also watches its own file, so a change to the job runs the job.
- The schedule runs daily at 04:30 UTC, away from the top of the hour and before the 05:00 UTC run of `ci.yml`.
- The concurrency group holds the event and the ref, so a newer push to a pull request cancels the old run, and a manual run does not cancel the schedule run.
- The workflow repeats the `env` of `ci.yml` (`DO_NOT_TRACK`, `UV_MANAGED_PYTHON`), because the job runs `uv` on the runner.
- The #1643 invariant keeps its checks of the build, the run in the image and the shards. It adds the trigger checks, and evaluates the `paths` patterns with `glob.translate`, where the last matching pattern decides and `!` excludes.

## Rejected alternatives
- A job-level `if:` on the output of a `dorny/paths-filter` job in `ci.yml`. It adds one job to each push, and the job of the suite then needs the filter job, so it no longer starts at once.
- A step-level filter, as the plan-only filter does. The job still takes a runner for each shard.
- Running only the tests that use real tools in the Service Image job. The issue marks it optional, and #4642 changes the same build.
