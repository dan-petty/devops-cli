## MODIFIED Requirements

### Requirement: The command names the first rule that stops each job
`devops roadmap explain <issue>` SHALL print, for the refine job, the stage job and the implement job, `yes` or `no`. For `no` it SHALL print the reason of the first rule that fails. The rules and their order SHALL be those of the job. The reasons SHALL be the texts of the "Left out" list of `stage --plan` and `implement --plan`, and, for refine, the wait of the item: what it waits for and what ends the wait. The rules are not an item or closed, the filter, and the rules of the job, then the limit of a run.

#### Scenario: An item of medium effort
- **WHEN** a Planned item holds `effort/medium` and the implement filter asks for `effort/low`
- **THEN** the implement job is `no` and the reason names the family `effort`, the value `low` that the filter takes, and the value `medium` that the item has

#### Scenario: A claimed item
- **WHEN** a Ready item that the filter names holds `owner/human`
- **THEN** the stage job and the implement job are `no`, and the reason is "It is claimed by human."

#### Scenario: A stopped item
- **WHEN** a Staged item holds `implement.stopped` and no retry comment follows
- **THEN** the implement job is `no` and the reason is the text of the stop

#### Scenario: An unplanned item
- **WHEN** a Ready item of low effort has no staged branch and no change folder on the default branch
- **THEN** the implement job is `no` and the reason says that it is neither Staged nor Planned, and the stage job is `yes`

#### Scenario: A recorded group over the budget
- **WHEN** the record of a Ready item holds `stage.needs_split` made with the file cap of now
- **THEN** the stage job is `no` and the reason is the text of the recorded split

#### Scenario: Not an item or closed
- **WHEN** the issue is closed, has no priority label, or does not exist
- **THEN** the three jobs are `no` and the reason says that it is closed or that it is no item

#### Scenario: The limit of a run
- **WHEN** an item passes every rule and the limit of a run is filled by items of higher priority
- **THEN** the job is `no` and the reason names the limit

#### Scenario: An item the job takes
- **WHEN** an item passes every rule within the limit
- **THEN** the job is `yes`

#### Scenario: An item that waits on a person in refine
- **WHEN** a New item's last refine round left a question for a person and no reply, closed issue or changed file follows
- **THEN** the refine job is `no` and the reason says that the item waits on a person and what makes refine look again

#### Scenario: An item the stage job returned twice
- **WHEN** a New item has `refine.returned_body_hash` equal to its `refine.body_hash` and a stage comment follows refine's last comment
- **THEN** the refine job is `no` and the reason says that the stage job returned the item twice on the same body

#### Scenario: A New item with no round
- **WHEN** a New item has no refine record
- **THEN** the refine job is `yes`
