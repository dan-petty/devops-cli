## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: An event with no scoped update stays a hint
`run_scoped_update` SHALL return None for an event or an action that has no row in `SCOPED_UPDATES`, and SHALL do nothing.

#### Scenario: A closed issue and a check suite that requests checks
- **WHEN** a delivery of `issues` `closed`, or of `check_suite` `requested`, is given
- **THEN** `run_scoped_update` returns None and the store records no write

#### Scenario: A closed issue and an opened pull request
- **WHEN** a delivery of `issues` `closed`, or of `pull_request` `opened`, is given
- **THEN** `run_scoped_update` returns None and the store records no write

### Requirement: The Service runs a subscribed event's scoped update on the lane of its table row
The roadmap consumer of the Service SHALL hand each subscribed webhook event that has a row in `SCOPED_UPDATES` and names an issue number or a pull request number to its scoped update, on the lane that holds the row of the update (`lane_of_row` with `service.lanes`). The delivery SHALL run the scoped update on the worker of that lane and SHALL queue no full round on any lane.

#### Scenario: A subscribed issues delivery runs on the triage lane
- **WHEN** a signed delivery of `issues` `opened`, `edited` or `reopened` with an issue number arrives, and the Service runs the default lanes
- **THEN** the Service runs the scoped update on the worker of the lane `intake`, and queues no full round on another lane

#### Scenario: A subscribed pull request delivery runs on the status lane
- **WHEN** a signed delivery of `pull_request` `synchronize` names pull request 42, and the Service runs the default lanes
- **THEN** the Service runs the scoped watch round on the worker of the lane `status`, and queues no full round on another lane

#### Scenario: An unscopeable event keeps a whole-round hint
- **WHEN** a signed delivery of `issues` with an action that is not in `SCOPED_UPDATES`, or a delivery that names no issue number and no pull request number, arrives
- **THEN** the Service enqueues a trigger on each lane as a whole-round hint
