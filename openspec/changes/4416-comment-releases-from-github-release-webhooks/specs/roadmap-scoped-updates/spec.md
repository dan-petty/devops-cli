## MODIFIED Requirements

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
