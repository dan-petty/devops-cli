## ADDED Requirements

### Requirement: A delivery that says that an issue left drops its record in each lane
A trigger of a delivery `issues` with the action `transferred` or `deleted` SHALL put the number of its issue in `TriggerBatch.left` of each lane that it wakes. A trigger of another event or action SHALL NOT. The round of a lane SHALL drop the record of each number of `TriggerBatch.left` from the listing of the lane before any row runs, with no GitHub read of that number, and SHALL log one warning for it.

#### Scenario: A batch names the numbers that left
- **WHEN** a lane worker gets the triggers `issues` `transferred` for 12, `issues` `labeled` for 14, `issues` `deleted` for 15 and `pull_request` `deleted` for 16 before a round
- **THEN** the batch of the round holds the subjects 12, 14, 15 and 16 and the left numbers 12 and 15, and the batch of a later trigger `issues` `edited` for 12 holds no left number

#### Scenario: The round of a lane drops the record
- **WHEN** the snapshot of a lane holds the open item 7, GitHub lists issue 7 no more, and `service_job` runs with a batch whose `left` holds 7
- **THEN** the store of the next round does not list item 7, the fake GitHub holds no request of `repos/acme/widgets/issues/7`, and the log holds the one line `#7 is no issue of acme/widgets now: a delivery says that it left. The lane status leaves it out.`

#### Scenario: A batch of another delivery drops nothing
- **WHEN** `service_job` runs with a batch of a delivery `issues` `labeled` for the subject 7
- **THEN** the store of the next round lists item 7
