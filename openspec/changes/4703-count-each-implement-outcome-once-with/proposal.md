# Proposal: #4703

## Why

The project review of #4679 needs an implement-delivery SLI, and #4703 shows that the Service counters of the implement Jobs do not agree with each other or with kube-state-metrics. The measured causes are these:

- The `result` label of `devops_cli_service_implement_jobs_total` holds the state of the Kubernetes Job. A runner that writes its own stop exits 0, so the Job is Complete and a failed attempt counts as `succeeded`. In the 72 hours to 2026-11-11T22:37Z the counter grew by 7 `succeeded` and 0 `failed`, while `devops_cli_service_implement_failures_total` grew by 5 (`limit_reached` 3, `conflict` 1, `test` 1). kube-state-metrics shows all 9 runner Jobs of that time as succeeded.
- A round reports only the Jobs of open items. The pull request of Job `devops-cli-runner-20261110-000512-7baf` merged at 00:33:15Z, about one minute after the Job ended, so its item closed first and no round reported or counted the Job.
- No check refuses an empty `repo` label.

## What Changes

- The `result` of an attempt is `failed` when the report finds a failure class, else the state of the Job. So each failure that the failures counter counts is also one `failed` attempt of the jobs counter.
- A round reports the Job of a closed item when the cluster still holds that Job. A closed item is no stop. A closed item whose Job is gone is not reported, so a deploy does not count old records again.
- `run_implement_round` refuses an empty `repo` with `RoadmapImplementError` before any request.

The change alters what the Service counts and reports, which a consumer observes, so it carries a spec delta.

## Capabilities

- `roadmap-implement-job`: the outcome counter rule changes, and two requirements are added.

## Impact

- `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/lang/en/messages.py` and their tests.
- `k8s/README.md` names the new meaning of the `result` label.
- After the deploy, a panel or a rule that reads `result="succeeded"` no longer includes the attempts that stopped.
- The change fits one pull request.

## Feasibility

The premise is partly confirmed. These are the checks against the real system, on 2026-11-11 with Prometheus and Loki through Grafana:

- `count by (repo) (last_over_time(devops_cli_service_implement_failures_total[7d]))` gives 19 series with no `repo`. The last sample of each is before 2026-11-05T17:29Z, from Service pods that ran before #3680 added the `repo` label. The current code always passes the repository of the round. So the empty label is old data, and this change adds the check that refuses it.
- `min(min_over_time(timestamp(devops_cli_service_implement_jobs_total)[8d:10m]))` is 2026-11-08T22:39Z: #4185 added the jobs counter then. 84 of the 93 runner Jobs that started in the 7 days to 2026-11-11T14:51:23Z started before that time. So most of the gap of 8 against 94 comes from the age of the counter, not from lost counts.
- Loki shows 94 lines `created devops-cli-runner-` and 93 rounds that reported 1 Job in those 7 days, so the Service creates all runner Jobs and reports almost all of them. Since 2026-11-09 it created 9 and reported 8; the ninth is the Job of a closed item, described in Why.
- `kube_job_status_succeeded` and `kube_job_status_failed` show 9 succeeded and 0 failed runner Jobs since 2026-11-09, while the Service recorded 5 stops in that time. A stop exits 0.

The acceptance check of the issue (the 7-day increase of the jobs counter within 10% of the runner Jobs that started) can run only 7 days after the deploy, because the counter is younger than its window.

## Existing Tool Considered

prometheus_client, already in use, holds the counters. kube-state-metrics, already deployed, gives the runner Job starts for the comparison. This is a fix of existing code with no new tool. It deletes the filter on open items in `_unreported` and the `state` argument of `_emit_implement_metrics`.
