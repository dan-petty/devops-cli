## MODIFIED Requirements

### Requirement: Drift CronWorkflow is daily
The `infra-drift` CronWorkflow SHALL run the `infra-drift` WorkflowTemplate once a day. It SHALL hold its cron expression in the list `spec.schedules` and SHALL NOT set `spec.schedule`, which the Argo Workflows controller v4 refuses with `SpecError`.

#### Scenario: Daily CronWorkflow passes the Kubernetes check
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the command prints `k8s: <N> cases, 0 failed`

#### Scenario: The render holds the plural schedules
- **WHEN** `kubectl kustomize k8s/devops` renders the product base
- **THEN** CronWorkflow `infra-drift` holds `schedules: ["0 6 * * *"]` and no `schedule`

#### Scenario: A Workflow of the CronWorkflow succeeds
- **WHEN** a person runs `kubectl -n devops get workflow -l workflows.argoproj.io/cron-workflow=infra-drift -o jsonpath='{.items[*].status.phase}'` after Argo CD syncs Application `devops` and one Workflow of `cronwf/infra-drift` ends
- **THEN** the command prints `Succeeded`

## ADDED Requirements

### Requirement: Drift WorkflowTemplate holds one mutex and the executor account
The `infra-drift` WorkflowTemplate SHALL hold its mutex `infra-drift` in the list `spec.synchronization.mutexes`, and SHALL NOT set `mutex` or `semaphore`. It SHALL set `spec.executor.serviceAccountName: argo-executor`, so the executor writes the task results with its own token. The pod SHALL keep the account `devops-cli`, which mounts no token.

#### Scenario: The WorkflowTemplate passes the Kubernetes check
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the command prints `k8s: <N> cases, 0 failed`

#### Scenario: The render holds the mutexes and the executor account
- **WHEN** `kubectl kustomize k8s/devops` renders the product base
- **THEN** WorkflowTemplate `infra-drift` holds `synchronization.mutexes: [{name: infra-drift}]`, `executor.serviceAccountName: argo-executor` and `serviceAccountName: devops-cli`, and no `synchronization.mutex`
