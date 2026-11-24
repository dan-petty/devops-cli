## ADDED Requirements

### Requirement: The roadmap consumer writes the cached issue before it wakes the lane
The roadmap consumer MUST write the issue of a subscribed `issues` event into the project brain from the event payload before it enqueues the wake of a row, and MUST send no GitHub request for that write.

#### Scenario: A labeled issue event writes the entry and wakes the row
- **WHEN** The roadmap consumer receives an `issues` event with action `labeled` for an issue of a Service repository.
- **THEN** The fake tier holds the new label set with the event time, and the fake lane trigger records one wake for the due row.
