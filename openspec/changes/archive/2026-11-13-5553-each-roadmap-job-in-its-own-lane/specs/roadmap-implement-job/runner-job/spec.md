## RENAMED Requirements

- FROM: `### Requirement: A model-lane round that has not ended does not delay the implement row`
- TO: `### Requirement: A round of another lane that has not ended does not delay the implement row`

## MODIFIED Requirements

### Requirement: A round of another lane that has not ended does not delay the implement row
The row `implement` SHALL run in a lane that holds no row that calls a model. A poll SHALL make it due by its interval, whether or not a round of another lane of the same repository is running. A suspended `implement` row in the ledger of failed rounds SHALL stay suspended until the hour ends, and a ledger record that holds an entry of the row SHALL load.

#### Scenario: The model lane is in a long refine round
- **WHEN** the lane of `refine`, a row of the earlier model lane, runs a refine round that has not ended, and a poll reaches each lane of the repository
- **THEN** the lanes of `metrics` and `implement` run their rows while the refine round is still running

#### Scenario: The rows of each lane
- **WHEN** the default lanes are read
- **THEN** the lane `implement` holds the row `implement` alone

#### Scenario: A suspended row keeps its suspension
- **WHEN** the record of failed rounds holds an entry of the row `implement` at the limit of rounds, and the lane of the row runs a round on the same input
- **THEN** the record loads, the row does not run, and the gauge `devops_cli_service_job_suspended` for the row is 1

#### Scenario: A suspended row runs again in a later hour
- **WHEN** the row `implement` failed its limit of rounds in a row, its fault is fixed, and a poll round of a later hour runs on the lane of the row
- **THEN** the row runs, with no webhook
