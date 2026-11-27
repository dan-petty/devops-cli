## ADDED Requirements

### Requirement: The watch row takes a plan pull request by its number and its head branch
The watch row SHALL take a pull request as the plan of an item only when the record of the item names the number of the pull request as `stage.pr` and its head branch as `stage.branch`, and `stage.branch` names the item. For a pull request whose head branch is not the recorded branch, the row SHALL send no write for the item of the record.

#### Scenario: A draft on the recorded branch
- **WHEN** the record of an open item names a green draft of the bot and the branch `feat/1-plan-the-rows`, and the head branch of the draft is that branch
- **THEN** the row marks the draft ready and records `stage.ready`

#### Scenario: A draft whose head branch is not the recorded branch
- **WHEN** the record of an open item names a green draft and the branch `feat/1-plan-the-rows`, and the head branch of the draft is `feat/4107-add-the-rows`
- **THEN** the draft is not the plan of the item, and the round sends no write, over GraphQL and over REST

#### Scenario: Two items record one number
- **WHEN** two open items record the number of one draft, and the head branch of the draft is the recorded branch of the second item
- **THEN** only the second item gets `stage.ready`

### Requirement: Each round of the watch row reads the head branch before it takes a plan
The GraphQL query of the watch row SHALL read the head branch of each open pull request (`headRefName`). The REST round and the scoped round SHALL read the pull request before they take the item of a record. The read of the plans that are no more open SHALL compare the head branch before it records `stage.ready` or sets a Status.

#### Scenario: The REST round reads a draft on the recorded branch
- **WHEN** the GraphQL quota is on hold, and the record of an open item names a green draft of the bot and its head branch
- **THEN** the row marks the draft ready

#### Scenario: A merged pull request on another branch
- **WHEN** the record of an open item names a pull request that merged and whose head branch is not the recorded branch
- **THEN** the round records no `stage.ready` for the item and sets no Status, in a reconciling round and in a scoped round

#### Scenario: A merged pull request on the recorded branch
- **WHEN** the record of an open item names a pull request that merged and whose head branch is the recorded branch
- **THEN** the round records `stage.ready` for the item
