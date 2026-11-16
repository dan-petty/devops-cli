# Proposal: #6018

## Why
A review after #5027 found that the queue of the fix-checks Jobs can waste or block the model places that implement and stage share (#6018). The TTL of 24 hours of an ended Job resets the retry cap. Two checks of one head start two Jobs. A waiting fix Job can hold a place for all time. A Kubernetes error fails the whole watch row. A Job that its deadline ended runs again. The Service writes to GitHub where the docstring says it writes nothing. The new panel can draw about 13 series.

## What Changes
- In mode `on`, the watch row writes the attempt, the outcome and the next allowed time of each reported fix unit in the item record `fix_checks.units`, keyed by `<pr>:<head>:<check>`. A unit with no Job reads them, so the TTL resets nothing. Mode `plan` writes no record (ADR 0021, rule 5).
- One pull request has at most one fix Job that runs or waits. The unit key keeps the check, and `--check` names it, as #5027 gives.
- A waiting fix Job holds a place only while its repository is in `service.repos` and it waited at most `roadmap.fix_checks.max_wait_minutes` (new, default 360). The watch row of each repository deletes an older waiting Job with a log line, and the policy `roadmap-service-job-deletes` admits that delete.
- The watch row catches a Kubernetes or a configuration error of the fix-checks round, logs it, counts it as `round_error`, and goes on.
- A Job that its deadline ended has the outcome `deadline` and gets no next attempt. The alert `RoadmapFixChecksJobWithoutResult` reads it.
- The watch row asks the step for its ready path only (`ready_only`): a check that fails between the two reads gives `skipped`, with no repair and no comment. The module docstring says what the Service writes.
- The panel `Service Fix-Checks Jobs by Result` draws 3 classes and Other.

A setting, a manifest, an alert, a panel and the Service behavior change, so the change has spec deltas.

## Capabilities
- `roadmap-fix-checks`: modified and added requirements.
- `roadmap-watch-row`: one modified and one added requirement.

## Impact
Code under `src/devops_cli/roadmap/`, `src/devops_cli/config/`, `src/devops_cli/server/counter_series.py` and the docstring of `src/devops_cli/k8s/cluster_job_api.py`; the admission policy and the Role comment of the Service; one alert rule and one panel; `docs/CLUSTER.md`, `docs/roadmap/job-success.md`, ADR 0021 and the generated setting tables. The change fits one pull request.

## Feasibility
The source of the base confirms each defect: `_next_attempt([])` gives 1 (`fix_checks_row.py`), `ttlSecondsAfterFinished: 86400` (`k8s/devops/cronjob-runner.yaml`), the check in the unit key, `model_slots` that counts each suspended fix Job, the unguarded call in `watch_round`, `_outcome` that gives `none` for `DeadlineExceeded`, and `run_fix_checks` that raises `RoadmapImplementError` with no repair. The tests of #6018 fail on the base. The Role allows `delete` on `jobs`, and the CEL of the delete policy reads `oldObject.spec.suspend`; the gate check `tests/gate/k8s_checks/job_admission_policy.py` evaluates it. Kubernetes stops the deadline timer of a suspended Job (Job `spec.suspend`), so only a delete ends the wait.

## Existing Tool Considered
Kueue (Apache-2.0, maintained) gives queues with a wait limit and quotas for suspended Jobs. It needs its own controller, CRDs and admission webhook, and it does not read the roadmap unit, the item record or the result line. Argo Workflows replaces the launcher seam after #4566. This change keeps the Kubernetes Job suspension that #5027 uses and adds about 200 lines; build cost about 0.6M tokens and 3 agent-hours. It deletes the Job-only attempt read of `_next_attempt` and the repository-blind count of `model_slots`.
