# roadmap-scoped-updates Specification

## Purpose
The update that a subscribed webhook event of the roadmap runs at once, scoped to what its delivery carries, and the record that keeps the reconciling poll from doing that update again or from skipping a change that it did not handle.

## Requirements

### Requirement: An issues delivery runs intake of its one issue
`run_scoped_update` SHALL run intake of the one issue that a delivery of the `issues` event with the action `opened`, `edited` or `reopened` names, on the triage lane, with intake's own decision code. It SHALL decide and write nothing for another issue.

#### Scenario: A delivery about one of three candidates
- **WHEN** a delivery of `issues` with the action `opened`, `edited` or `reopened` names candidate 2 of three candidates
- **THEN** the model judges candidate 2 alone, and only candidate 2 gets labels and a reason comment

#### Scenario: An edit of an issue that is already an Item
- **WHEN** a delivery of `issues` `edited` names an issue that holds a `priority/*` label, and no other candidate is open
- **THEN** the model judges nothing, the store records no write, and no intake record is written

### Requirement: An event with no scoped update stays a hint
`run_scoped_update` SHALL return None for an event or an action that has no row in `SCOPED_UPDATES`, and SHALL do nothing.

#### Scenario: A closed issue and an opened pull request
- **WHEN** a delivery of `issues` `closed`, or of `pull_request` `opened`, is given
- **THEN** `run_scoped_update` returns None and the store records no write

### Requirement: A scoped update writes no last success
A scoped update SHALL write no job's last success to `schedule.json`.

#### Scenario: Scoped intake after an earlier intake round
- **WHEN** intake's last success is half an hour old and a delivery of `issues` `opened` runs its scoped update
- **THEN** `schedule.json` holds the same last success for intake as before

### Requirement: The reconciling poll decides a lost delivery and not a handled one
After a scoped intake, the next poll SHALL run intake when another fresh candidate is open, also before intake's hourly interval. That intake SHALL decide the other candidate and SHALL not decide the issue of the scoped update again.

#### Scenario: One delivered and one lost event
- **WHEN** the delivery of candidate 2 runs its scoped update, the delivery of candidate 1 (`opened` or `reopened`) is lost, and a poll comes five minutes later, before intake's interval
- **THEN** the poll runs intake, the model judges candidate 1, and the model judged candidate 2 only once, in the scoped update

### Requirement: A scoped update keeps the record that a capped round left
Scoped intake SHALL add the issue that it decided to the intake record, SHALL keep every other entry, and SHALL keep intake due when the record was due.

#### Scenario: A scoped update after a capped round
- **WHEN** a round decides five of seven candidates and leaves a fresh one, and a delivery of candidate 6 runs its scoped update
- **THEN** the record holds the entries of candidates 1 to 6 and stays due, and the next poll decides candidate 7 alone

### Requirement: The requests of a scoped update name its job row
`run_scoped_update` SHALL run the runner of a scoped update in the request scope of the update's job. Each model request and GitHub request of the update SHALL carry that job as its `row` label, the same row as the job counter of the update.

#### Scenario: A scoped intake sends a model request
- **WHEN** a delivery of `issues` `opened` runs its scoped intake, and the model answers through `LLMClient`
- **THEN** the points of `devops_cli_ai_requests_total`, `devops_cli_ai_tokens_total` and `devops_cli_ai_spend_usd_total` carry `row` `intake`, and none carries `other`

### Requirement: A new issue makes intake due at the next poll
The poll SHALL run intake when the repository has an issue newer than the newest issue that the intake record keeps, also before intake's interval. An intake round SHALL keep the newest issue as the round starts. A scoped update SHALL keep it as it was. A newer pull request SHALL not make intake due.

#### Scenario: The delivery of a new issue is lost
- **WHEN** intake decided candidate 1, candidate 2 opens, no scoped update runs for it, and a poll comes five minutes later
- **THEN** the poll runs intake and the model judges candidate 2

#### Scenario: A new pull request
- **WHEN** a pull request opens after the last intake round, and no issue opens
- **THEN** the next poll runs no intake

#### Scenario: The scoped update decided the new issue
- **WHEN** the scoped update of new candidate 2 decided it, and a poll comes four minutes later
- **THEN** the poll runs intake, the model judges nothing in that round, and the poll after it runs no intake

### Requirement: The Service runs a subscribed event's scoped update on the lane of its table row
The roadmap consumer of the Service SHALL hand each subscribed webhook event that carries an issue number and has a row in `SCOPED_UPDATES` to its scoped update, on the lane that the table names. The delivery SHALL run the scoped update on the worker of that lane and SHALL queue no full round on any lane.

#### Scenario: A subscribed issues delivery runs on the triage lane
- **WHEN** a signed delivery of `issues` `opened`, `edited` or `reopened` with an issue number arrives
- **THEN** the Service runs the scoped update on the triage lane worker
- **AND** the Service queues no full round on the status lane or the model lane

#### Scenario: An unscopeable event keeps a whole-round hint
- **WHEN** a signed delivery of `issues` with an action that is not in `SCOPED_UPDATES`, or without an issue number, or of another subscribed event arrives
- **THEN** the Service enqueues a trigger on each lane as a whole-round hint

### Requirement: An edit of an Item wakes the model lane
After the scoped update of an `issues` `edited` delivery, the Service SHALL enqueue the trigger `("webhook", "issues", "edited")` on the model lane alone. The `refine` and `retitle` rows SHALL declare that key.

#### Scenario: An edit of an issue that holds a priority label
- **WHEN** a signed `issues` `edited` delivery names an open issue with the label `priority/p2-medium`, and the scoped intake writes nothing
- **THEN** the model lane runs a round in which `refine` and `retitle` are due, and the status lane and the triage lane run no round

### Requirement: A critical placement wakes the model lane
After a scoped update that places a critical fix or a P0 item, the Service SHALL enqueue the delivery's key on the model lane alone, so the round runs `refine` from `refine_due`.

#### Scenario: An opened issue that intake places as a P0 item
- **WHEN** a signed `issues` `opened` delivery names an issue that the scoped intake places as a P0 item
- **THEN** `schedule.json` holds a `refine_due` stamp, and the model lane runs a round in which `refine` is due

### Requirement: A webhook key makes only the rows that declare it due
A row of the due table SHALL be due by a webhook key only when its `batch_keys` hold that key. `refine` SHALL declare `edited`, `labeled` and `unlabeled`, `retitle` SHALL declare `edited`, and `stage` and `implement` SHALL declare `labeled`, `unlabeled` and `closed`, each as an `issues` key.

#### Scenario: A labeled delivery
- **WHEN** every row is fresh by its interval and a signed `issues` `labeled` delivery arrives
- **THEN** `refine`, `stage` and `implement` are due, and `intake`, `retitle` and `alternatives` are not
