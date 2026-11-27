## ADDED Requirements

### Requirement: The k8s row runs the offline lint of Argo on the Argo objects
The `k8s` row of `devops ci` SHALL run `argo lint --offline` on the objects of the rendered product base, and SHALL fail when the lint names a problem. The lint refuses each singular field that the Argo Workflows controller v4 refuses or does not read: `schedule` of a CronWorkflow, or `synchronization.mutex` or `synchronization.semaphore` of a Workflow spec or of one of its templates. A lint that cannot run SHALL fail the row.

#### Scenario: Each singular field gives one finding
- **WHEN** the check gives the lint one fixture object: a CronWorkflow with `spec.schedule`, a WorkflowTemplate with `spec.synchronization.mutex` or `spec.templates[0].synchronization.mutex`, a Workflow with `spec.synchronization.semaphore`, or a CronWorkflow with `spec.workflowSpec.synchronization.semaphore`
- **THEN** it gives one finding, and the finding names the kind and the name of the object and that field

#### Scenario: The plural fields and a CronJob give no finding
- **WHEN** the check gives the lint fixture objects with `schedules`, `mutexes` and `semaphores`, and a CronJob of `batch/v1` with `spec.schedule`
- **THEN** it gives no finding

#### Scenario: The product base
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the row passes only when `argo lint --offline` names no problem in the Argo objects of `k8s/devops`
