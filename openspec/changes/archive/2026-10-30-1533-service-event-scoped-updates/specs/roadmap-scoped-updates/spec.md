## ADDED Requirements

### Requirement: The Service hands a subscribed event to its scoped update
The roadmap consumer of the Service SHALL hand each subscribed webhook event that carries an issue number and has a row in `SCOPED_UPDATES` to its scoped update, on the lane that the table names. The delivery SHALL run the scoped update on the worker of that lane and SHALL queue no full round on any lane.

#### Scenario: A subscribed issues delivery runs on the model lane
- **WHEN** a signed delivery of `issues` `opened`, `edited` or `reopened` with an issue number arrives
- **THEN** the Service runs the scoped update on the model lane worker
- **AND** the Service queues no full round on the status lane or the model lane

#### Scenario: An unscopeable event keeps a whole-round hint
- **WHEN** a signed delivery of `issues` with an action that is not in `SCOPED_UPDATES`, or without an issue number, or of another subscribed event arrives
- **THEN** the Service enqueues a trigger on each lane as a whole-round hint
