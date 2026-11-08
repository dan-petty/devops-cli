# Spec Delta

## MODIFIED Requirements

### Requirement: Each item of a stage round counts once by its result
A stage round, whether the Service or the command runs it, SHALL add 1 to `devops_cli_roadmap_stage_total` for each item it handled, with the label `result`: `staged` for an item written as a branch and a draft, `needs_split` for an item stopped on a group over the budget, `failed` for an item that failed in the plan or in the writes, and `skipped` for an item the job left out with a reason. An item SHALL count under one result.

#### Scenario: Four results in one round
- **WHEN** a round stages one item, stops one on the budget, fails one in the model call, and leaves one out for an open dependency
- **THEN** the counter has one point each for `staged`, `needs_split`, `failed` and `skipped`

#### Scenario: A returned item
- **WHEN** a round plans one item and the model answers with the key `premise_failed` twice
- **THEN** the item counts as `failed`, and the counter has no point for `returned`

#### Scenario: A plan with no write
- **WHEN** `devops roadmap stage --plan` runs
- **THEN** the counter has no point

#### Scenario: A staged item carries its repository
- **WHEN** A stage round counts a staged item for repository `owner/repo`.
- **THEN** The series `devops_cli_roadmap_stage_total{repo="owner/repo",result="staged"}` increases by one and no `devops_cli_roadmap_pipeline_plans_total` series exists.
