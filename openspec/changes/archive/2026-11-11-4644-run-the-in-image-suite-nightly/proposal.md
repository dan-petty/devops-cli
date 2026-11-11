# Proposal: #4644

## Why
Service Image Tests runs the same tests as Tests & Coverage, in 6 jobs, on each push to a pull request. On 4 PR runs of 2026-11-11 it used 30.5 to 45.9 of the 52.4 to 100.8 runner-min of a run (measured). In 100 failed PR runs, it found no test failure that Tests & Coverage did not find. The account runs at most 20 hosted jobs at one time, so these jobs make the queue of each pull request longer. Owner decision O1 of 2026-11-11 takes the suite off the path of each push and reverses Direction B of #1643. Closes #4644.

## What Changes
- The job `service-image-test` moves from `ci.yml` to a new workflow, `service-image-test.yml`, with no change to its build and test steps.
- The workflow runs on the daily schedule, on `workflow_dispatch`, and on a pull request that changes `Dockerfile`, `.dockerignore`, `pyproject.toml`, `uv.lock`, `src/devops_cli/tools_lock/**` or the workflow. The native `paths` filter stops the run before a runner starts.
- The step filter for plan-only pull requests goes, because the `paths` filter does not match a plan.
- The #1643 invariant reads the new workflow and also requires the schedule, the manual run, the image inputs, and no run for a change to `src/` only.
- `docs/SDLC.md` states the new triggers.

## Capabilities
- New: `ci-service-image-tests`.

## Impact
- A push to a pull request that changes only `src/` starts 0 Service Image Tests jobs (from 6).
- A defect that only the Python or the OS of the image shows appears in the next daily run, up to 24 hours after the merge.
- The release pull request changes `pyproject.toml` and `uv.lock`, so it still runs the suite, as it does today. #4637 removes the jobs that are not required from the release pull request.
- The jobs are not required checks, so no ruleset changes.

## Feasibility
- GitHub documents that `on.pull_request.paths` decides whether the workflow runs at all: when no changed file matches, GitHub starts no run and no job. A step filter starts the job and takes a runner.
- `ci.yml` on `origin/main` holds the job with `if: workflow_dispatch || pull_request` and a step-level `dorny/paths-filter` that skips only plan-only changes.
- The Actions API for 4 successful PR runs of `ci.yml` (2026-11-11) lists 23 jobs, 21 that ran, of which 6 are Service Image Tests.
- `.dockerignore` lets only `pyproject.toml`, `uv.lock`, `README.md` and `src/` into the build context. The `Dockerfile` installs the tools from `src/devops_cli/tools_lock`.

## Existing Tool Considered
GitHub Actions `schedule`, `workflow_dispatch` and the native `paths` filter. No new tool. The invariant matches the `paths` patterns with `glob.translate` of the standard library.
