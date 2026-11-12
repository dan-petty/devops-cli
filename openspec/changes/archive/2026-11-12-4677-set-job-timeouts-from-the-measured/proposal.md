# Proposal: #4677

## Why

The job limits of `ci.yml` were 2.6 to 129 times the longest run of the job. `DevContainer Image` had a limit of 60 minutes for a longest run of 7 minutes. The account runs at most 20 hosted jobs at one time, so a hung job held a runner for 30 to 60 minutes, and the jobs of other pull requests waited. No step had a limit of its own. A hung gate or test step thus ran until the job limit cancelled the job, and the log did not name the step that hung. The owner rule of 2026-11-11 says that each inner limit is shorter than the limit around it: one test < its step < its job. Closes #4677.

## What Changes

- `ci.yml`: set each job limit to about two times the longest run of the job, and 5 minutes at least. Static Analysis 6, the test shards 20, Tests & Coverage 5, Test Job Duration 5, DevContainer Image 20, the Service, Runner and MCP Server images 12, Dependency Freshness 5, Changed-Test Independence 15, and Rule Pack Tests, Docs Site Build, Image Pins and Third-Party Image Scan 5.
- `ci.yml`: give the Static Analysis Quality Gate step a limit of 3 minutes and the Tests & Coverage Quality Gate step of each shard a limit of 17 minutes.
- `service-image-test.yml`: set the job limit to 20 minutes and give the step that runs the suite in the image a limit of 14 minutes.
- `tests/invariants/test_workflow_contracts.py`: hold the job limits and the step limits, hold the step limit of each test step above the hang bound of one test, and hold each step limit under the limit of its job in every workflow.
- The change alters CI workflows and their tests only, and no behavior that a consumer of `devops` observes, so it has no spec delta.

## Capabilities

None. The change edits two workflows and their contract tests.

## Impact

- `.github/workflows/ci.yml`, `.github/workflows/service-image-test.yml` and `tests/invariants/test_workflow_contracts.py`.
- A green run takes the same time. A hung job gives its runner back after 20 minutes or less, not 30 to 60 minutes.
- A slow runner can stop a job that works. The limits are about two times the longest run, and a `timed_out` job in the 2 weeks after the merge shows a limit that is too short.
- The `codeql.yml` job keeps its limit of 15 minutes from #4651. It is under 20 minutes.
- The row timeout of `devops ci` (1800 s) is still longer than the 17-minute step limit of a shard. The item that gives the test row its own bound (900 s) puts it under this step limit.

## Feasibility

- The longest runs come from the Actions API: 4,774 jobs of the `ci.yml` runs of 2026-11-07 to 2026-11-11, read with `devops gh api repos/<owner>/<repo>/actions/runs/<id>/jobs`. The longest run of each job and step is in the comments of `JOB_LIMIT_MINUTES` and `SUITE_STEP_LIMIT_MINUTES`.
- Changed-Test Independence ran up to 797 s before #4509. In the 23 runs on a head that holds the #4509 merge, it ran up to 174 s, so the issue's value of 15 minutes applies now.
- Rule Pack Tests and Third-Party Image Scan did their work in no job of that window. Their last runs that did the work took 35 s (2026-10-17) and 47 s (2026-11-07).
- The runner gives a step that passes its `timeout-minutes` the result Failed, with the message "The action '<step>' has timed out after <n> minutes", and evaluates the conditions of the later steps (`src/Runner.Worker/StepsRunner.cs` of actions/runner, `RunStepAsync`). A job cancellation gives the running step the result Canceled.
- `[tool.pytest.ini_options]` of `pyproject.toml` sets `timeout = 600`, the hang bound of one test. The test steps have limits of 14 and 17 minutes, so one test < its step < its job.

## Existing Tool Considered

GitHub Actions `timeout-minutes` at the job and at the step (native). The change builds no tool and deletes no internal code.
