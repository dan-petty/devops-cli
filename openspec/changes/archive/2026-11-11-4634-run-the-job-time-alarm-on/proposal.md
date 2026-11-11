# Proposal: #4634

## Why

The job `Test Job Duration` of `ci.yml` runs on each push to `main`, and each time it reads almost the same window of 20 runs. The mean of that window is over 300 s, so each push run of `main` fails in this job. Thus `main` has no green run, and a new failure on `main` hides behind the red alarm. The metric also counts the time in the queue: the account runs a fixed number of hosted jobs at one time, so a shard or the join can wait minutes for a runner, and that wait is not the time of the tests. The daily schedule run shares the concurrency group of the pushes to `main`, so a merge can cancel the one run that the alarm needs. Closes #4634.

## What Changes

- The job `job-time` of `ci.yml` runs only on `schedule` and `workflow_dispatch`. No push run and no pull request run holds it.
- The concurrency group of `ci.yml` holds `github.event_name`, so a push to `main` does not cancel the schedule run of `main`.
- `devops ci job-time` times a run as the run time of the slowest shard job plus the run time of the join job `Tests & Coverage`. The rest of the span is the queue time of the run. The command prints it in a column and its mean on its own line, and the limit does not count it.
- The limit stays 300 s, and the window stays 20 runs.

## Capabilities

- `ci-job-time` (modified): the time of a run without the queue, the queue line, and the triggers of the job.

## Impact

- A push run of `main` is green when its tests and other checks pass.
- The alarm runs once a day and on a manual run. It still exits 1 while the mean run time is over 300 s: on 2026-11-11 it reads 499 s (it read 584 s with the queue).
- `ci.yml` starts one job less on each push to `main`.
- No setting, secret or repository setting changes. The required checks keep their names.

## Feasibility

- Actions API, `GET /repos/dan-petty/devops-cli/actions/workflows/ci.yml/runs?branch=main&event=push&status=completed&per_page=30`, read on 2026-11-11: 21 runs cancelled, 9 failed, 0 passed. In each of the 9 failed runs, the only failed job is `Test Job Duration` (`GET .../actions/runs/<id>/jobs`).
- Actions API, schedule runs of `ci.yml`: run 42963886166 of 2026-11-11 05:09 UTC concluded `cancelled`. The group was `ci-${{ github.workflow }}-${{ github.ref }}` (`ci.yml:18-20`), the same for a push to `main` and the schedule run of `main`.
- Actions API, jobs of run 43018142394: the four shards started at 12:12:49, 12:14:33, 12:17:53 and 12:19:41 UTC and ran 427, 341, 360 and 310 s. The join started at 12:28:19 and ran 45 s. The old metric gave 975 s. The new one gives 472 s and a queue time of 503 s. The `started_at` of a job is its start on a runner, as the spread of the shard starts shows.
- `ci.yml`: the join job has `needs: test-shard`, so it starts after the last shard ends, and the queue time is never negative.
- GitHub Actions concurrency accepts any expression of the `github` context in `concurrency.group`. `ci.yml` already uses `github.workflow` and `github.ref` there.
- Command run, 2026-11-11, `devops ci job-time --repo dan-petty/devops-cli`: before, mean 584 s; after, mean 499 s and mean queue time 85 s, exit 1 both times.

## Existing Tool Considered

GitHub Actions `schedule`, `workflow_dispatch` and `concurrency` (native), and the `started_at` and `completed_at` fields of the Actions jobs API that the client already reads. No new tool. Cost: about 40,000 tokens and 2 hours to build, no upkeep beyond the metric. The change deletes the push trigger of the job.
