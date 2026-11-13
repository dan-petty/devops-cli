# Proposal

## Why

The stage job ran in the pod of the roadmap Service. About 19 releases and ConfigMap edits a day restart that pod (Recreate), and 53 of 71 restarts from 2026-11-07 to 2026-11-13 stopped a running stage round: 3 of 11 stage items staged in 24 hours on 2026-11-13 (`devops_cli_roadmap_stage_total`). Part 1 (#5483) added the stage Job template, its admission, its entry point and its check-in. This change (part 2 of #4559) makes the Service submit one stage Job for each Ready item, and removes the in-pod path, so a rollout of the Service stops no plan.

## What Changes

- The row `stage` moves from the model lane to the status lane, after `stage_ready`, and becomes a submit (`src/devops_cli/roadmap/stage/stage_submit.py`, in the form of `implement_submit.py`). It plans no item and calls no model.
- A round lists the stage Jobs of the repository by the component, owner and repository labels: the Job list is the lock. It recovers each check-out whose Job ended with no check-in: `evicted` (the Job is gone), `deadline` (`DeadlineExceeded`, or a Job that still runs 600 s after the deadline of the check-out, which the row deletes), `failed` (pod failure policy or backoff limit, classed by the exit code in the message of the condition and the tail of the log), and `succeeded` (a lost check-in).
- The round then runs the current cleanup (orphans, staged branches of closed items, rejections of the items that it does not submit) and the normal selection, with each item that a running Job works on left out (new reason `stage_job`), up to the new setting `roadmap.stage.jobs` (default 1) less the Jobs that run. For each item it writes the check-out with the claim `owner/service`, then creates the Job named from the item and the hash of its body. A 409 means the Job exists. An ended Job of the same name is deleted first, only when the failure wait of the item allows the retry.
- An eviction is free 3 times on one body (`stage.evictions`). A `deadline` end, a `failed` end and a later eviction record the failure marks and count toward `roadmap.stage.plan_defect_limit` on the body. The end that reaches the limit returns the item to New with a comment that asks refine to split it (owner rule 2). The Job's own `deadline` check-in counts the same way. The check-in of a Job and of the row releases the claim `owner/service`.
- The Service counts `devops_cli_service_stage_jobs_total` by `repo`, `result` and `class`, and the row `Roadmap Service` of the dashboard charts it.
- `ClusterJob` carries the labels and the reason and the message of the condition `Failed`. `ClusterJobs.create` raises `ClusterJobExistsError` on 409.
- Removed: the in-pod body of `_run_stage_adapter`, the row `stage` of `MODEL_LANE_ROWS`, `raise_for_failed_round`, and the use of the model clone by stage (`devops roadmap stage` and the Job use the status clone, `status_clone`).
- Telemetry: the rules that read the series of the planner (GitHub requests and writes, model requests, web searches, tool calls) select `job=~"roadmap-service|roadmap-stage"`. The job grade report and the panels of the row `Roadmap Job Success` read the result lines of the stage Job pods too.
- About 1,300 changed lines.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/job`: the Service submits and recovers the stage Jobs, and a counted end can return the item for a split.
- `roadmap-stage/round`: the stage job no longer runs on the model lane, and the row no longer fails for the items that a round tried.
- `roadmap-stage/fix-plan`: the row `fix_plan` follows `retitle`.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_submit.py` (new), `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_job.py`, `src/devops_cli/roadmap/stage/stage_pending.py`, `src/devops_cli/roadmap/stage/stage_left_out.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/job_grade_report.py`, `src/devops_cli/k8s/cluster_job.py`, `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/exceptions/k8s.py`, `src/devops_cli/server/counter_series.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/config/`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/docs/generator.py`.
- Manifests: `k8s/devops/monitoring/prometheus-rules-values.yaml`, `k8s/devops/dashboards/devops-cli.json`, `k8s/devops/configmap.example.yaml`.
- Documents: `docs/CLUSTER.md`, `docs/roadmap/stage.md`, `docs/roadmap/job-success.md`, `docs/roadmap/intake.md`, `docs/ROADMAP_WORKFLOW.md` and the generated references.
- Overlap: #5026 swaps the cleanup of the row for `steps/cleanup.py`; #5440 owns the `roadmap.stage` limits that the split rule reuses (`plan_defect_limit`); #4558 relabels the runner Job in `cluster_job.py`; #5411 changes the review gates of `stage.py` in other hunks.
- Secrets and settings: no new Secret key. No setting is removed. The new setting `roadmap.stage.jobs` has a default, so no ConfigMap change comes before the image rolls.

## Feasibility

- Part 1 (#5483) is on the base branch: CronJob `roadmap-stage`, the policy rows that admit the create and the delete of a stage Job by the Service, `stage_job_name`, `stage_job_labels`, `stage_job_env`, `ClusterJobs.delete_job`, `--job-item` and the check-in keys.
- Loki on 2026-11-13: the stream of a Job pod has the labels `app_kubernetes_io_name="devops-cli-job"` and `container`, and the Service and runner pods have the containers `service` and `runner`. The selector `{namespace="devops", app_kubernetes_io_name=~"roadmap-service|devops-cli-job", container=~"service|stage"}` reads the Service and the stage Jobs and no runner pod.
- The message of a condition `Failed` with the reason `PodFailurePolicy` names the exit code of the container (Kubernetes: `Container <name> for pod <ns>/<pod> failed with exit code <n> matching FailJob rule at index <i>`).
- The planner run tool (#4003, #4098) stays off: `stage_run_allowlist.py` has no import in `src`.

## Existing Tool Considered

Kubernetes Jobs, `podFailurePolicy` and the label selector of the API are the lock and the retry, as the implement Job uses them (#2667). The change builds only the submit and the recovery: about 200,000 tokens and 6 hours to build, about 10,000 tokens a month to keep, and about 30,000 tokens to fix. It removes the in-pod path of the stage row.
