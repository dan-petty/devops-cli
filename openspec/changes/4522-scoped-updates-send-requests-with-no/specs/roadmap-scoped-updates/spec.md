## ADDED Requirements

### Requirement: The requests of a scoped update name its job row
`run_scoped_update` SHALL run the runner of a scoped update in the request scope of the update's job. Each model request and GitHub request of the update SHALL carry that job as its `row` label, the same row as the job counter of the update.

#### Scenario: A scoped intake sends a model request
- **WHEN** a delivery of `issues` `opened` runs its scoped intake, and the model answers through `LLMClient`
- **THEN** the points of `devops_cli_ai_requests_total`, `devops_cli_ai_tokens_total` and `devops_cli_ai_spend_usd_total` carry `row` `intake`, and none carries `other`
