# Design

## Decisions
- A workflow of its own with the native `on.pull_request.paths` filter. GitHub evaluates the filter before it starts a run, so a pull request that changes only `src/` or only a plan starts no job.
- The inputs are the files that the build reads other than `src/`: the build definition under `.devcontainer/`, `.dockerignore`, `pyproject.toml`, `uv.lock`, `README.md` and `src/devops_cli/tools_lock/**`. The tool locks hold the pins that the Dockerfile copies and the pin of the Dev Containers CLI that builds the image. The workflow also watches the two actions and its own file, as the old filter watched them and `ci.yml`.
- The schedule runs daily at 04:15 UTC, after the 04:00 UTC cleanup of the devcontainer images and before the 04:30 UTC Service Image Tests and the 05:00 UTC run of `ci.yml`.
- The concurrency group holds the event and the ref, so a newer push to a pull request cancels the old run, and a manual run does not cancel the schedule run.
- The checkout fetches one commit. The full history served only the `git diff` of the old step filter.
- The invariant reads the `COPY` sources of `.devcontainer/Dockerfile`, so a new copied file that the filter does not hold fails the test. The tree `src/` is the one source that it does not require. The trigger check of the #4644 invariant takes the workflow and its inputs as arguments, and both invariants use it.

## Rejected alternatives
- A job-level `if:` on the output of a `dorny/paths-filter` job in `ci.yml`. It adds one job to each push, and the image job then needs the filter job, so it no longer starts at once.
- Keeping the step filter and removing only `src`. The job still takes a runner on each push.
- Removing `README.md` from the inputs. The package build reads it, and the Dockerfile copies it. Of the last 131 merged pull requests, few changed it.
