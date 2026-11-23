## ADDED Requirements

### Requirement: An issue comment delivery runs the row that its text wakes
The roadmap consumer SHALL run the scoped update that `scoped_update_of` gives a trusted `issue_comment` delivery, on the lane of that row: the `implement` row when the comment body is the retry command, and the `refine` row otherwise. The row's own predicate SHALL decide its work, and the delivery SHALL queue no whole round on any lane and SHALL write no due mark.

#### Scenario: A retry comment clears the stop and submits a Job
- **WHEN** a test delivers a signed trusted `implement: retry` comment for a Blocked issue that holds a Service stop
- **THEN** `scoped_update_of` gives the `implement` row, the stop clears through the retry rule, and the row submits one runner Job

#### Scenario: A trusted reply runs the refine row
- **WHEN** a test delivers a signed trusted comment that is not the retry command on an open issue
- **THEN** `scoped_update_of` gives the `refine` row, `plan_refine` reads that one item number, and no whole round is queued on any lane

## MODIFIED Requirements

### Requirement: The Service runs a subscribed event's scoped update on the lane of its table row
The roadmap consumer of the Service SHALL hand each subscribed webhook event that `scoped_update_of` gives an update and that names an issue number or a pull request number to that scoped update, on the lane that holds the row of the update (`lane_of_row` with `service.lanes`). The delivery SHALL run the scoped update on the worker of that lane and SHALL queue no full round on any lane.

#### Scenario: A subscribed issues delivery runs on the triage lane
- **WHEN** a signed delivery of `issues` `opened`, `edited` or `reopened` with an issue number arrives, and the Service runs the default lanes
- **THEN** the Service runs the scoped update on the worker of the lane `intake`, and queues no full round on another lane

#### Scenario: A subscribed pull request delivery runs on the status lane
- **WHEN** a signed delivery of `pull_request` `synchronize` names pull request 42, and the Service runs the default lanes
- **THEN** the Service runs the scoped watch round on the worker of the lane `status`, and queues no full round on another lane

#### Scenario: An unscopeable event keeps a whole-round hint
- **WHEN** a signed delivery of `issues` with an action that is not in `SCOPED_UPDATES`, or a delivery that names no issue number and no pull request number, arrives
- **THEN** the Service enqueues a trigger on each lane as a whole-round hint
