# Proposal

## Why

The stage job runs in the pod of the roadmap Service (#5483, part 1 of 2 of #4559). About 19 releases and ConfigMap edits a day restart that pod (Recreate), and 53 of 71 restarts from 2026-11-07 to 2026-11-13 stopped a running stage round: Prometheus showed 3 staged and 8 failed stage items in 24 hours on 2026-11-13 (`devops_cli_roadmap_stage_total`). Before the Service can submit one stage Job for each item (part 2, #4559), the cluster must admit a stage Job, and the stage command must plan one item in a Job. This change adds both, with no change to the rows of the Service, so a person can run and measure one stage Job after the release.

## What Changes

- A suspended CronJob `roadmap-stage` is the template of the stage Job: the Service image in container `stage`, ServiceAccount `devops-cli` with no token, 2 keys of Secret `devops-cli` through `secretKeyRef` (the private key of the App and the key of the gateway, no MCP token while `roadmap.stage.mcp` is off) and no `envFrom`, 250m CPU and 1 Gi requested and 1 CPU and 2 Gi at most, `activeDeadlineSeconds: 10800`, and `backoffLimit: 2` with a `podFailurePolicy` that ignores a disruption and fails the Job on each exit code but 75.
- The admission policy `roadmap-service-jobs` gets the variable `stage` (a name that starts with `devops-cli-stage-`) and checks a stage Job with its own rules for the image, the secret keys, the retries, the resources and the component label. A runner Job keeps every rule, and may not carry the stage component or a `podFailurePolicy`. The new policy `roadmap-service-job-deletes` admits the `DELETE` of a stage Job by the Service and refuses any other.
- The Role `roadmap-service-jobs` gets `delete` on `jobs` and `get` on CronJob `roadmap-stage`.
- `searxng-stage-clients` and `searxng-perimeter` admit the pod of a stage Job to SearXNG on TCP 8080, for the tool `search_web` of the planner. A runner Job pod still cannot reach SearXNG.
- `STAGE_TEMPLATE`, `TemplateName.STAGE` and the builders `stage_job_name`, `stage_job_labels` and `stage_job_env` (ADR 0022 names and labels). `ClusterJobs.delete_job` deletes a Job with the propagation `Background`, and a Job that is gone is no error.
- `devops k8s run-job --template stage --repo <owner/name> --item <n>` makes a stage Job by hand.
- `devops roadmap stage --job-item <n> --confirm` is the entry point of the Job: the selection of a round narrowed to the item, one model call slot, a GitHub request budget of the new setting `roadmap.stage.github_requests_per_hour`, a time budget of the new setting `roadmap.stage.time_budget_seconds` cut to the deadline of the Job less 1800 s, `sigterm_raises`, and the exit codes 0, 1, 75 and 143.
- The record keys `stage.job`, `stage.job_at`, `stage.job_deadline` and `stage.job_result`: the Job checks in at its end only when the check-out names it. A removal or a rejection of a plan keeps them.
- The pod of a Job that runs again judges the intent mark of its own Job at once, removes the branch and stages the item in the same run.
- `ensure_checkout(blobless=True)` clones with `--filter=blob:none` for the Job.
- The change carries a spec delta in the new capability `roadmap-stage/job`, because a manifest, a command option and the behavior of a Job are observable.
- The change fits one pull request: about 1,400 changed lines, more than half of them tests. Part 2 (#4559) switches the Service to the Job and removes the in-pod path.

## Capabilities

### New Capabilities

- `roadmap-stage/job`: the stage Job of one item: its template, its admission, its entry point, its budgets, its ends and its check-in.

### Modified Capabilities

None.

## Impact

- Manifests: `k8s/devops/cronjob-stage.yaml`, `k8s/devops/kustomization.yaml`, `k8s/devops/roadmap-service/admissionpolicy.yaml`, `k8s/devops/roadmap-service/role.yaml`, `k8s/devops/searxng/networkpolicy-client.yaml`, `k8s/devops/searxng/networkpolicy.yaml`.
- Code: `src/devops_cli/k8s/cluster_job.py`, `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/k8s/api.py`, `src/devops_cli/commands/k8s/cluster_jobs.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_pending.py`, `src/devops_cli/roadmap/stage/stage_job.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/`.
- Documents: `docs/CLUSTER.md`, `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md` and the generated references.
- Overlap: #4558 labels the runner Job in `cluster_job.py` with the same `RepoRef` builders; #5440 changes the `roadmap.stage` settings; #5411 changes the review gates of `stage.py` in other hunks.
- Secrets and settings: the 2 keys exist in the live Secret `devops/devops-cli` on 2026-11-13 (the key names only were read). No setting is removed, and the new settings have defaults, so no Secret or ConfigMap change comes before the image rolls.

## Feasibility

- The stage row runs in the Service pod: `src/devops_cli/roadmap/run.py:def _run_stage_adapter` calls `plan_stage` with `StageWriter` in the model lane.
- The cluster runs Kubernetes v1.37.2+k3s1, so `podFailurePolicy` (GA in 1.31) and ValidatingAdmissionPolicy with `variables` (GA in 1.30) are available.
- `kubectl -n devops get secret devops-cli -o go-template` with the key names only listed `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, `DEVOPS_CLI_AI_API_KEY` and `DEVOPS_CLI_MCP_STAGE_TOKEN` on 2026-11-13.
- `src/devops_cli/roadmap/attempt_kill.py` (#5413) gives the kill classes and the exit codes 75 and 143. `src/devops_cli/roadmap/time_budget.py` gives `TimeBudget`, and the planner already checks it before each model call (`_Planner._check_budget`).
- `RepoRef.unit_name` and `RepoRef.adhoc_name` (ADR 0022) give names with the prefix `devops-cli-stage-` of 63 characters at most.
- `stage_run_allowlist.py` is imported by no module of `src/`, so the planner run tool has no wiring in a stage Job.
- The gate check `tests/gate/k8s_checks/devops_runtime.py` renders the homelab overlay with the kustomize image override of Image Updater and finds the digest on container `stage`.

## Existing Tool Considered

Kubernetes Jobs with `podFailurePolicy`, ValidatingAdmissionPolicy, NetworkPolicy and the runner Job pattern of #2667 cover the need. The change builds only the glue: about 120,000 tokens and 4 hours to build, about 5,000 tokens a month to keep, and about 20,000 tokens to fix. It deletes no code: part 2 (#4559) removes the in-pod path of the stage row.
