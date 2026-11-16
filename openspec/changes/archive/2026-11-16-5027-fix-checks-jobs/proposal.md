# Proposal: #5027

## Why
A finished bot pull request that fails a check later waits for a person: only the runner Job calls the step `fix-checks`, and the Job ends at the ready mark (#5027). The owner wakes to about 20 failed Service pull requests a day and wants the fixer Jobs to run (tracker #5014). The watch row must start one fix-checks Job for each such pull request, before new implement and stage work, under the shared limit of the model Jobs.

## What Changes
- A launcher seam, `src/devops_cli/roadmap/job_launcher.py`, builds the Job of a row from the suspended CronJob `devops-cli-runner` with the args, the size and the labels of the row. The implement row uses it too. Only the implement Job carries `implement-repo`.
- `due_steps` routes a FAILED bot pull request whose failed check has the class test, lint, types or plan check to `fix_checks`. The watch row starts one Job for it, named `RepoRef.unit_name(fix-checks, "<pr>:<head>:<check>", item)`, so a second create gets 409.
- `roadmap.model_jobs` (default 2) bounds the implement, stage and fix-checks Jobs together. A fix Job with no free place waits suspended and holds its place, so the fix goes first.
- `roadmap.fix_checks.mode` (`off`, `plan`, `on`; default `plan`). The ConfigMap template sets `on`, by the owner direction of 2026-11-16.
- The deadline of a fix Job is the step limit plus 1800 s, and the limits nest under 14400 s.
- The row reports each ended fix Job once, from its result line. A Job with no result line is `none`, fires `RoadmapFixChecksJobWithoutResult`, and gets the next attempt within `roadmap.implement.continuations_per_item`.
- The step takes `--check`, does not stop on `owner/service`, and gives `skipped` when the lease refuses a push because the head moved. A SIGTERM exits 75. `fix-conflict` reads `owner/service` in lower case.
- The watch row treats a runner Job as live only while no round reported it (`job_holds`). It runs the ready path of the step on a delivery draft only after a fix Job repaired it, once for each head.
- The implement repair loop no longer writes the `fix_checks.*` counts.

The command, the settings, the manifests and the Service behavior change, so the change has spec deltas.

## Capabilities
- `roadmap-fix-checks`: modified and added requirements.
- `roadmap-watch-row`: the `due_steps` requirement is modified.

## Impact
Code under `src/devops_cli/roadmap/`, `src/devops_cli/k8s/`, `src/devops_cli/config/` and `src/devops_cli/server/counter_series.py`; the ConfigMap template; one alert rule and one dashboard panel; `docs/CLUSTER.md`, `docs/TELEMETRY.md`, `docs/roadmap/job-success.md` and ADR 0021. The change fits one pull request.

## Feasibility
The admission policy admits a runner Job with any args, a deadline up to 14400 s, `backoffLimit: 0` and `spec.suspend` (`k8s/devops/roadmap-service/admissionpolicy.yaml`); the gate check `tests/gate/k8s_checks/job_admission_policy.py` evaluates the manifest of the seam in both modes and suspended. The Role allows `patch` on `jobs`, which resumes a Job. A suspended Job starts no pod, and its deadline counts from the resume (Kubernetes Job `spec.suspend`, GA in 1.24). The step's command, fixers and guards exist (#5976, #5986).

## Existing Tool Considered
Argo Workflows (Apache-2.0, maintained, in use) gives retries, deadlines and semaphores, and a `WorkflowLauncher` replaces this seam after #4566. It lacks the roadmap glue: the due predicate, the unit name and its 409, the plan mode, the report of the result line and the order of fix Jobs before new units. Kubernetes Job suspension (the queue that Kueue uses) holds the waiting fix Jobs, so no queue of our own is built. Build cost: about 1.2M tokens and 1 agent-day. The change deletes the direct `jobs.create` call of `implement_submit._create` and the `fix_checks.*` writes of the implement repair loop.
