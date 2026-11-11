## REMOVED Requirements

### Requirement: The Service hands a subscribed event to its scoped update
**Reason**: The requirement named the model lane for the scoped update, and the update runs on the triage lane. The next requirement replaces it under a name that states the lane.
**Migration**: Read "The Service runs a subscribed event's scoped update on the lane of its table row".

## ADDED Requirements

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
