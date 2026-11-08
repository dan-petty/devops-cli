## ADDED Requirements

### Requirement: Qdrant Secret scoped to the ingest pods
The stack SHALL reference the Qdrant credential Secret from the ingest WorkflowTemplate only.

#### Scenario: Secret references of the stack
- **WHEN** The offline manifest test renders k8s/devops and reads the secret references of every workload.
- **THEN** The test asserts that only the ingest WorkflowTemplate names the Qdrant Secret.

### Requirement: Network policy selects only the ingest pods
The stack MUST select only the ingest pods for traffic to Qdrant on port 6333, on egress from the ingest pods and on ingress to Qdrant.

#### Scenario: Pod selectors of the Qdrant rules
- **WHEN** The offline manifest test reads the Qdrant egress and ingress rules and the pod labels of the stack.
- **THEN** The test asserts that both rules select the ingest pods only and name TCP port 6333.

### Requirement: One ingest run at a time
The ingest WorkflowTemplate MUST hold the global `rag-ingest` mutex, and the CronWorkflow MUST set `concurrencyPolicy: Forbid`.

#### Scenario: Overlap is impossible
- **WHEN** The offline manifest test reads the WorkflowTemplate and the CronWorkflow.
- **THEN** The test asserts that `spec.synchronization.mutex.name` is `rag-ingest` and `spec.concurrencyPolicy` is `Forbid`.

### Requirement: Schedule follows the poll interval
The CronWorkflow MUST use the shortest whole-minute cron period that is not shorter than `service.poll_interval_seconds`.

#### Scenario: Default poll interval
- **WHEN** `service.poll_interval_seconds` holds its default of 151 seconds.
- **THEN** The test asserts that the rendered schedule is `*/3 * * * *`.

### Requirement: One embedding request at a time
The ingest template MUST set `ai.gateway_concurrency.embedding` to 1.

#### Scenario: Embedding concurrency of the template
- **WHEN** The offline manifest test reads the environment of the ingest template.
- **THEN** The test asserts that the template sets the embedding concurrency to 1.

### Requirement: Lag alert
The stack MUST ship a `RagIngestBehind` alert on the ingest freshness metric.

#### Scenario: Alert rule present
- **WHEN** The offline manifest test reads the alert rules of the stack.
- **THEN** The test asserts that one rule named `RagIngestBehind` reads the freshness metric and fires after two schedule periods without a success.

### Requirement: Stack command renders the resources
`devops k8s deploy-stack --stack all` MUST render the ingest WorkflowTemplate and the CronWorkflow.

#### Scenario: Rendered stack
- **WHEN** The offline test renders the stack with `--dry-run`.
- **THEN** The rendered output holds the WorkflowTemplate and the CronWorkflow in namespace `devops`.
