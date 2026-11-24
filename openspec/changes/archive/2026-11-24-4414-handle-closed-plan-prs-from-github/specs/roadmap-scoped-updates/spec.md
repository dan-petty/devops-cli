## ADDED Requirements

### Requirement: A closed plan pull request wakes the lanes of its rows
After the scoped watch round of a `pull_request` `closed` delivery, the Service SHALL enqueue the trigger `("webhook", "pull_request", "closed")`, with the pull request as its subject, on each lane of the repository but the lane of the update. When `service.lanes` puts another row into the lane of the update, the Service SHALL also enqueue the trigger on that lane.

#### Scenario: A closed plan pull request wakes the lanes of its rows
- **WHEN** a signed `pull_request` `closed` delivery names pull request 42 and the scoped watch round runs on the lane `watch`
- **THEN** the Service enqueues the trigger `("webhook", "pull_request", "closed")` with 42 as its subject on each lane but the lane `watch`

## MODIFIED Requirements

### Requirement: A webhook key makes only the rows that declare it due
A row of the due table SHALL be due by a webhook key only when its `batch_keys` hold that key. `refine` SHALL declare `edited`, `labeled` and `unlabeled`, `retitle` SHALL declare `edited`, and `stage` and `implement` SHALL declare `labeled`, `unlabeled` and `closed` as `issues` keys and `closed` as a `pull_request` key.

#### Scenario: A labeled delivery
- **WHEN** every row is fresh by its interval and a signed `issues` `labeled` delivery arrives
- **THEN** `refine`, `stage` and `implement` are due, and `intake`, `retitle` and `alternatives` are not

#### Scenario: A closed plan pull request makes the stage and implement rows due
- **WHEN** every row of the due table is fresh by its interval and the batch holds the key `("webhook", "pull_request", "closed")`
- **THEN** the `stage` and `implement` rows are due, and each other row of the due table is not due
