## MODIFIED Requirements

### Requirement: One ingest run at a time
The ingest WorkflowTemplate MUST hold the global `rag-ingest` mutex in the list `spec.synchronization.mutexes`, and MUST NOT set `synchronization.mutex` or `synchronization.semaphore`, which the Argo Workflows controller v4 does not read. The CronWorkflow MUST set `concurrencyPolicy: Forbid`.

#### Scenario: Overlap is impossible
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the row passes, and it prints no finding for WorkflowTemplate `devops/rag-ingest` or CronWorkflow `devops/rag-ingest`

#### Scenario: The render holds the mutexes
- **WHEN** `kubectl kustomize k8s/devops` renders the product base
- **THEN** WorkflowTemplate `rag-ingest` holds `synchronization.mutexes: [{name: rag-ingest}]` and no `synchronization.mutex`, and CronWorkflow `rag-ingest` holds `concurrencyPolicy: Forbid`

### Requirement: Schedule follows the poll interval
The CronWorkflow MUST use the shortest whole-minute cron period that is not shorter than `service.poll_interval_seconds`. It MUST hold the cron expression in the list `spec.schedules`, and MUST NOT set `spec.schedule`, which the Argo Workflows controller v4 refuses with `SpecError`.

#### Scenario: Default poll interval
- **WHEN** `service.poll_interval_seconds` holds its default of 151 seconds and `kubectl kustomize k8s/devops` renders the product base
- **THEN** CronWorkflow `rag-ingest` holds `schedules: ["*/3 * * * *"]` and no `schedule`

#### Scenario: A Workflow of the CronWorkflow succeeds
- **WHEN** a person runs `kubectl -n devops get workflow -l workflows.argoproj.io/cron-workflow=rag-ingest -o jsonpath='{.items[*].status.phase}'` after Argo CD syncs Application `devops` and one Workflow of `cronwf/rag-ingest` ends
- **THEN** the command prints `Succeeded`

## ADDED Requirements

### Requirement: The ingest executor has its own account
The ingest WorkflowTemplate SHALL set `spec.executor.serviceAccountName: argo-executor`, so the executor writes the task results with its own token. The pod SHALL keep the account `devops-cli`, which mounts no token.

#### Scenario: The render holds the executor account
- **WHEN** `kubectl kustomize k8s/devops` renders the product base
- **THEN** WorkflowTemplate `rag-ingest` holds `executor.serviceAccountName: argo-executor` and `serviceAccountName: devops-cli`

### Requirement: The ingest step retries exit 75 only
The template `ingest` of the ingest WorkflowTemplate MUST set a `retryStrategy` with `limit: "3"` and `expression: "asInt(lastRetry.exitCode) == 75"`, so only exit 75 retries, at most three times.

#### Scenario: The render holds the retry rule
- **WHEN** `kubectl kustomize k8s/devops` renders the product base
- **THEN** the template `ingest` of WorkflowTemplate `rag-ingest` holds `retryStrategy.limit: "3"` and `retryStrategy.expression: asInt(lastRetry.exitCode) == 75`
