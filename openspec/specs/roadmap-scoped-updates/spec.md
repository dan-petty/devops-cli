# roadmap-scoped-updates Specification

## Purpose
The update that a subscribed webhook event of the roadmap runs at once, scoped to what its delivery carries, and the record that keeps the reconciling poll from doing that update again or from skipping a change that it did not handle.

## Requirements

### Requirement: An issues delivery runs intake of its one issue
`run_scoped_update` SHALL run intake of the one issue that a delivery of the `issues` event with the action `opened`, `edited` or `reopened` names, on the triage lane, with intake's own decision code. It SHALL decide and write nothing for another issue.

#### Scenario: A delivery about one of three candidates
- **WHEN** a delivery of `issues` with the action `opened`, `edited` or `reopened` names candidate 2 of three candidates
- **THEN** the model judges candidate 2 alone, and only candidate 2 gets labels

#### Scenario: An edit of an issue that is already an Item
- **WHEN** a delivery of `issues` `edited` names an issue that holds a `priority/*` label, and no other candidate is open
- **THEN** the model judges nothing, the store records no write, and no intake record is written

### Requirement: An event with no scoped update stays a hint
`run_scoped_update` SHALL return None for an event or an action that has no row in `SCOPED_UPDATES`, and SHALL do nothing.

#### Scenario: A closed issue and a check suite that requests checks
- **WHEN** a delivery of `issues` `closed`, or of `check_suite` `requested`, is given
- **THEN** `run_scoped_update` returns None and the store records no write

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
The roadmap consumer of the Service SHALL hand each subscribed webhook event that `scoped_update_of` gives an update to that scoped update, on the lane that holds the row of the update (`lane_of_row` with `service.lanes`), when the delivery names an issue number, when it names a pull request number, or when it carries the release of a `release` delivery. The delivery SHALL run the scoped update on the worker of that lane and SHALL queue no full round on any lane.

#### Scenario: A subscribed issues delivery runs on the triage lane
- **WHEN** a signed delivery of `issues` `opened`, `edited` or `reopened` with an issue number arrives, and the Service runs the default lanes
- **THEN** the Service runs the scoped update on the worker of the lane `intake`, and queues no full round on another lane

#### Scenario: A subscribed pull request delivery runs on the status lane
- **WHEN** a signed delivery of `pull_request` `synchronize` names pull request 42, and the Service runs the default lanes
- **THEN** the Service runs the scoped watch round on the worker of the lane `status`, and queues no full round on another lane

#### Scenario: An unscopeable event keeps a whole-round hint
- **WHEN** a signed delivery of `issues` with an action that is not in `SCOPED_UPDATES`, or a delivery that names no issue number, no pull request number and carries no release, arrives
- **THEN** the Service enqueues a trigger on each lane as a whole-round hint

### Requirement: An edit of an Item wakes the other lanes
After the scoped update of an `issues` `edited` delivery, the Service SHALL enqueue the trigger `("webhook", "issues", "edited")`, with the issue as its subject, on each lane of the repository but the lane of the update. When `service.lanes` puts another row into the lane of the update, the Service SHALL also enqueue the trigger on that lane. The `refine` and `retitle` rows SHALL declare that key.

#### Scenario: An edit of an issue that holds a priority label
- **WHEN** a signed `issues` `edited` delivery names an open issue with the label `priority/p2-medium`, and the scoped intake writes nothing
- **THEN** the lanes of `refine` and `retitle` run a round in which their row is due, each other lane but the lane `intake` runs a round with no due row, and the lane `intake` runs no round

#### Scenario: An edit when intake shares its lane
- **WHEN** `service.lanes` is `{model: [intake, refine]}`, and a signed `issues` `edited` delivery names an open issue
- **THEN** the scoped update runs on the lane `model`, and then the lane `model` and each other lane get the trigger with the issue as its subject

### Requirement: A critical placement wakes the other lanes
After a scoped update that places a critical fix or a P0 item, the Service SHALL enqueue the delivery's key, with the issue as its subject, on each lane of the repository but the lane of the update, so the lane of `refine` runs `refine` from `refine_due`. When `service.lanes` puts another row into the lane of the update, the Service SHALL also enqueue the key on that lane.

#### Scenario: An opened issue that intake places as a P0 item
- **WHEN** a signed `issues` `opened` delivery names an issue that the scoped intake places as a P0 item
- **THEN** `schedule.json` holds a `refine_due` stamp, and the lane of `refine` runs a round in which `refine` is due

### Requirement: A webhook key makes only the rows that declare it due
A row of the due table SHALL be due by a webhook key only when its `batch_keys` hold that key. `refine` SHALL declare `edited`, `labeled` and `unlabeled`, `retitle` SHALL declare `edited`, and `stage` and `implement` SHALL declare `labeled`, `unlabeled` and `closed` as `issues` keys and `closed` as a `pull_request` key.

#### Scenario: A labeled delivery
- **WHEN** every row is fresh by its interval and a signed `issues` `labeled` delivery arrives
- **THEN** `refine`, `stage` and `implement` are due, and `intake`, `retitle` and `alternatives` are not

#### Scenario: A closed plan pull request makes the stage and implement rows due
- **WHEN** every row of the due table is fresh by its interval and the batch holds the key `("webhook", "pull_request", "closed")`
- **THEN** the `stage` and `implement` rows are due, and each other row of the due table is not due

### Requirement: A pull request, review or check suite delivery runs the watch row scoped to its pull requests
`SCOPED_UPDATES` SHALL hold a row for each action that a pull request, a pull request review or a check suite delivery carries, with the job `watch` and a runner that runs `watch_round` narrowed to the pull request numbers of the delivery, on the lane of the row `watch`. The runner SHALL write no job's last success, and a delivery of the App's own bot SHALL run no scoped update.

#### Scenario: A pull request delivery runs the scoped watch round
- **WHEN** a signed `pull_request` delivery with the action `synchronize` names pull request 42, and the store holds open staged drafts 42 and 43
- **THEN** the scoped update runs `watch_round` for pull request 42 and reads no pull request 43

#### Scenario: A check suite delivery names every pull request of the suite
- **WHEN** a signed `check_suite` delivery with the action `completed` holds pull requests 42 and 43
- **THEN** the delivery names 42 and 43, and the scoped round reads both

#### Scenario: A delivery that matches no staged draft sends no request
- **WHEN** a signed delivery names pull request 99, and no open item records pull request 99
- **THEN** the scoped round sends no `GET pulls` request and no check-runs request, and returns the empty round result

#### Scenario: A delivery of the App's own bot starts nothing
- **WHEN** a signed `pull_request` delivery carries the login of the App's bot as its sender
- **THEN** the consumer refuses the delivery and runs no scoped update

### Requirement: An issue comment delivery runs the row that its text wakes
The roadmap consumer SHALL run the scoped update that `scoped_update_of` gives a trusted `issue_comment` delivery, on the lane of that row: the `implement` row when the comment body is the retry command, and the `refine` row otherwise. The row's own predicate SHALL decide its work, and the delivery SHALL queue no whole round on any lane and SHALL write no due mark.

#### Scenario: A retry comment clears the stop and submits a Job
- **WHEN** a test delivers a signed trusted `implement: retry` comment for a Blocked issue that holds a Service stop
- **THEN** `scoped_update_of` gives the `implement` row, the stop clears through the retry rule, and the row submits one runner Job

#### Scenario: A trusted reply runs the refine row
- **WHEN** a test delivers a signed trusted comment that is not the retry command on an open issue
- **THEN** `scoped_update_of` gives the `refine` row, `plan_refine` reads that one item number, and no whole round is queued on any lane

### Requirement: A closed plan pull request wakes the lanes of its rows
After the scoped watch round of a `pull_request` `closed` delivery, the Service SHALL enqueue the trigger `("webhook", "pull_request", "closed")`, with the pull request as its subject, on each lane of the repository but the lane of the update. When `service.lanes` puts another row into the lane of the update, the Service SHALL also enqueue the trigger on that lane.

#### Scenario: A closed plan pull request wakes the lanes of its rows
- **WHEN** a signed `pull_request` `closed` delivery names pull request 42 and the scoped watch round runs on the lane `watch`
- **THEN** the Service enqueues the trigger `("webhook", "pull_request", "closed")` with 42 as its subject on each lane but the lane `watch`
