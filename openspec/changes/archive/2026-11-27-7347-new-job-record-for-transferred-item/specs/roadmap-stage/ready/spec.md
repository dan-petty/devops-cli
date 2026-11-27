## ADDED Requirements

### Requirement: The stage ready round takes a plan pull request by its number and its head branch
The round of `mark_stage_ready` SHALL read a pull request only for an item whose record names a plan: the number of `stage.pr`, and a `stage.branch` that names the item. It SHALL take the pull request as that plan only when its head branch is `stage.branch`. For any other pull request the round SHALL mark nothing ready and SHALL send no record write.

#### Scenario: A green draft on another branch
- **WHEN** the record of an open item names a green draft and the branch `fix/1-the-job-drops-a-comment`, and the head branch of the draft is `feat/4107-add-the-rows`
- **THEN** the round sends no `gh pr ready` and no record write, and names the item in no outcome

#### Scenario: A merged pull request on another branch
- **WHEN** the record of an open item names a pull request that merged and whose head branch is not the recorded branch
- **THEN** the round records no `stage.ready` and sets no Status
