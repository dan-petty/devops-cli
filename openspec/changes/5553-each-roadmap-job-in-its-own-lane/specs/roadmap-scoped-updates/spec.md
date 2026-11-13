## RENAMED Requirements

- FROM: `### Requirement: An edit of an Item wakes the model lane`
- TO: `### Requirement: An edit of an Item wakes the other lanes`
- FROM: `### Requirement: A critical placement wakes the model lane`
- TO: `### Requirement: A critical placement wakes the other lanes`

## MODIFIED Requirements

### Requirement: The Service runs a subscribed event's scoped update on the lane of its table row
The roadmap consumer of the Service SHALL hand each subscribed webhook event that carries an issue number and has a row in `SCOPED_UPDATES` to its scoped update, on the lane that holds the row of the update (`lane_of_row` with `service.lanes`). The delivery SHALL run the scoped update on the worker of that lane and SHALL queue no full round on any lane.

#### Scenario: A subscribed issues delivery runs on the triage lane
- **WHEN** a signed delivery of `issues` `opened`, `edited` or `reopened` with an issue number arrives, and the Service runs the default lanes
- **THEN** the Service runs the scoped update on the worker of the lane `intake`
- **AND** the Service queues no full round on another lane

#### Scenario: An unscopeable event keeps a whole-round hint
- **WHEN** a signed delivery of `issues` with an action that is not in `SCOPED_UPDATES`, or without an issue number, or of another subscribed event arrives
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
