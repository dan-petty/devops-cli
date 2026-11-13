# roadmap-stage/job Specification

## Purpose
The stage Job of one item: the CronJob template that it comes from, the admission and the network rules of its pod, the command that it runs, its budgets, its exit codes, and the check-in that it writes on the item.

## Requirements

### Requirement: The stage CronJob is the template of a stage Job
The manifests SHALL hold a suspended CronJob `roadmap-stage` in namespace `devops` whose container `stage` runs the Service image with ServiceAccount `devops-cli` and no token, takes 2 keys of Secret `devops-cli` and no `envFrom`, gives its pod 120 s after a SIGTERM, and runs its pod again only after exit 75 or a disruption.

#### Scenario: The rendered template
- **WHEN** the gate check renders `k8s/devops` with kustomize.
- **THEN** CronJob `roadmap-stage` holds the keys `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` and `DEVOPS_CLI_AI_API_KEY` through `secretKeyRef` and no MCP token, `terminationGracePeriodSeconds: 120`, 250m CPU and 1Gi requested, 1 CPU and 2Gi as limits, `activeDeadlineSeconds: 10800`, `backoffLimit: 2`, a `podFailurePolicy` that ignores `DisruptionTarget` and fails the Job on each exit code but 75, the telemetry name `roadmap-stage` and the pod labels `app.kubernetes.io/name: devops-cli-job` and `app.kubernetes.io/component: roadmap-stage`.

### Requirement: The admission policy admits a stage Job of the Service with its own rules
The policy `roadmap-service-jobs` SHALL check a Job of the Service whose name starts with `devops-cli-stage-` with the rules of a stage Job, and every other Job with the rules of a runner Job.

#### Scenario: The Job of the template passes
- **WHEN** the policy judges the Job that `build_job` makes from CronJob `roadmap-stage`.
- **THEN** no rule refuses it.

#### Scenario: A stage Job that breaks one rule
- **WHEN** the stage Job has the runner image, an `envFrom`, a third key, an MCP token or another Secret in `secretKeyRef`, a `fieldRef` or a `configMapKeyRef`, a token mount, another ServiceAccount, `backoffLimit: 2` with no `podFailurePolicy`, a deadline other than 10800, other args than `roadmap stage --repo <owner/name> --job-item <n> --confirm`, a plain environment name that is not in the template or in `stage_job_env`, a token repository other than the repository of `--repo` or none, other resources, or no component label.
- **THEN** one rule refuses it.

#### Scenario: A runner Job with a rule of a stage Job
- **WHEN** a runner Job has `backoffLimit: 2`, the `podFailurePolicy` of a stage Job, or the component label `roadmap-stage`.
- **THEN** one rule refuses it.

### Requirement: The Service deletes a stage Job and no other Job
The policy `roadmap-service-job-deletes` SHALL admit the `DELETE` of a Job by the Service only when the Job has a name that starts with `devops-cli-stage-` and the label `app.kubernetes.io/component: roadmap-stage`, and the Role `roadmap-service-jobs` SHALL allow `delete` on `jobs` and `get` on CronJob `roadmap-stage`. `ClusterJobs.delete_job` SHALL delete with the propagation `Background` and treat a Job that is gone as deleted.

#### Scenario: The delete of a stage Job and of a runner Job
- **WHEN** the Service deletes a stage Job, and then a runner Job.
- **THEN** the policy admits the first delete and refuses the second.

#### Scenario: A Job that is gone
- **WHEN** `delete_job` names a Job that the API does not hold.
- **THEN** it returns with no error.

### Requirement: The pod of a stage Job reaches SearXNG
The NetworkPolicies SHALL let a pod with the labels `app.kubernetes.io/name: devops-cli-job` and `app.kubernetes.io/component: roadmap-stage` send to SearXNG on TCP 8080, and SearXNG SHALL admit it. A runner Job pod SHALL NOT reach SearXNG.

#### Scenario: The pods that reach SearXNG
- **WHEN** the gate check judges the Service pod, the pod of a stage Job and the pod of a runner Job.
- **THEN** the first two reach SearXNG on TCP 8080, and the third does not.

### Requirement: The stage Job has a name and labels of its item
`stage_job_name` SHALL give the unit name of the row `stage` for the repository, the item and the plan key, with at most 63 characters, and the same inputs SHALL give the same name. The Job and its pod SHALL carry the component, owner, repository and item labels of ADR 0022.

#### Scenario: The Job of an item
- **WHEN** `build_job` makes the Job of item 42 from the stage template.
- **THEN** the args go to container `stage`, the Job and the pod carry the four labels, and the name is the same for the same plan key and differs for another key or item.

### Requirement: The job item keeps every rule of a round
`devops roadmap stage --job-item <n> --confirm` SHALL select item `n` with every rule of a round: an item with a rejected plan, an item in the wait of its failure class and an item with a recorded split stay out with the reason of a round. `--item` SHALL keep its overrides. `--job-item` SHALL need `--confirm` and refuse `--item`.

#### Scenario: A held item
- **WHEN** the item has a rejected plan, a recent failure or a recorded split.
- **THEN** the job item leaves it out with the kind of a round, and `--item` selects it.

#### Scenario: A refused option
- **WHEN** a person passes `--job-item` with `--item`, with `--plan`, or with no mode.
- **THEN** the command exits 1 and calls no model.

### Requirement: The stage Job holds its budgets
The entry point SHALL set one model call slot, install a GitHub request budget of `roadmap.stage.github_requests_per_hour` for the process, and plan with a time budget of `roadmap.stage.time_budget_seconds` cut to `roadmap.stage.job_deadline` less 1800 seconds. The settings SHALL refuse a time budget above 9000 or not above `roadmap.mcp.timeout_seconds`.

#### Scenario: The budgets of a run
- **WHEN** a stage Job plans an item with a request budget of 1.
- **THEN** the process has one model call slot, the draft pull request takes the one place of the budget, and the next request waits.

#### Scenario: The time that is left
- **WHEN** the deadline of the Job ends 3000 seconds from now and the setting is 9000.
- **THEN** the time budget is 1200 seconds.

### Requirement: A stage Job that acts as the App plans only with a token for its repository
The entry point SHALL refuse to run, before a clone, a model call or a write, when the process holds the private key of the GitHub App and `service.github_app.token_repository` is not the repository of `--repo` (case-insensitive). A process that does not hold the key SHALL run with the token of its person.

#### Scenario: No token repository or another one
- **WHEN** a stage Job holds the key of the App and its token repository is unset or names another repository.
- **THEN** it raises an error that names the setting, makes no model call and keeps the check-out.

#### Scenario: A person's run
- **WHEN** the process does not hold the key of the App.
- **THEN** the check passes.

### Requirement: The stage Job ends with the exit code of its end and checks in
The entry point SHALL exit 0 for a result, 1 for a failure of the item, 75 for a SIGTERM before the time budget ends, and 143 for a SIGTERM after it or a time budget that ends before a model call. Except after a SIGTERM before the time budget ends, it SHALL write `stage.job_result` and clear `stage.job`, `stage.job_at` and `stage.job_deadline` in one write, only when `stage.job` names the Job of the pod. A `deadline` end SHALL record the failure with the class `timeout`.

#### Scenario: A normal end
- **WHEN** the Job stages its item and the check-out names the Job.
- **THEN** it exits 0, the record holds `stage.job_result` with the result `staged`, and the check-out is clear.

#### Scenario: The check-out of another Job
- **WHEN** the check-out names another Job.
- **THEN** the Job writes no `stage.job_result` and the check-out stays.

#### Scenario: An eviction
- **WHEN** SIGTERM comes before the time budget ends.
- **THEN** the command exits 75 and the check-out stays.

#### Scenario: The deadline
- **WHEN** SIGTERM comes after the time budget ends.
- **THEN** the command exits 143, the record holds the result `deadline` and the failure class `timeout`, and the check-out is clear.

### Requirement: A pod that runs again removes the orphan of its own Job
When the check-out of the item names the Job of the pod, the stage SHALL judge the intent mark `stage.pending` of the item at any age, remove its branch and stage the item in the same run. Every other mark SHALL keep the age rule, and a removal or a rejection of a plan SHALL keep the keys of the check-out.

#### Scenario: The pod after an eviction
- **WHEN** the item holds a young mark and a pushed branch of the identity of the session, and the check-out names the Job.
- **THEN** the run removes the branch, stages the item with one draft pull request, and the record holds no `stage.pending`.

#### Scenario: The young mark of another Job
- **WHEN** the check-out names another Job.
- **THEN** the run removes nothing and leaves the item out as held.

### Requirement: The stage Job clones with no blobs
`ensure_checkout` with `blobless` SHALL clone with `--filter=blob:none`, and the default clone SHALL take every blob.

#### Scenario: The two clones
- **WHEN** a blobless checkout and a default checkout clone the repository.
- **THEN** the first clone command holds `--filter=blob:none` and the second does not.
