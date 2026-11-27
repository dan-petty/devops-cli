## ADDED Requirements

### Requirement: The k8s row refuses the singular fields of the Argo objects
The `k8s` row of `devops ci` SHALL fail when an object of the group `argoproj.io` in the rendered product base sets a singular field that the Argo Workflows controller v4 refuses or does not read: `schedule` of a CronWorkflow, or `synchronization.mutex` or `synchronization.semaphore` of a Workflow spec or of one of its templates. Each finding SHALL name the object and the path of the field.

#### Scenario: Each singular field gives one finding
- **WHEN** the rule reads one fixture object: a CronWorkflow with `spec.schedule`, a WorkflowTemplate with `spec.synchronization.mutex` or `spec.templates[main].synchronization.mutex`, a Workflow with `spec.synchronization.semaphore`, or a CronWorkflow with `spec.workflowSpec.synchronization.semaphore`
- **THEN** it gives one finding, and the finding names the kind, the namespace and the name of the object and that field

#### Scenario: The plural fields and a CronJob give no finding
- **WHEN** the rule reads fixture objects with `schedules`, `mutexes` and `semaphores`, and a CronJob of `batch/v1` with `spec.schedule`
- **THEN** it gives no finding

#### Scenario: The product base
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the row passes only when no Argo object of `k8s/devops` sets a singular field
