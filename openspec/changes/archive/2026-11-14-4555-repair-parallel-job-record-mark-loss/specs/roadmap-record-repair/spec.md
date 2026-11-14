# roadmap-record-repair Specification

## Purpose
`GitHubRoadmapStore` verifies that marks written to an issue's job record persist after an update. When concurrent writes overwrite a mark, the store repairs the lost mark by merging it into the current record and writing again.

## ADDED Requirements

### Requirement: A lost mark is repaired
`GitHubRoadmapStore` SHALL read the issue record back after sending a `PATCH` request. When any mark that the writer set is missing from the record, the store SHALL read the issue again, merge the missing marks, and send another `PATCH`.

#### Scenario: Two stores interleave one write
- **WHEN** two stores on one GitHub fake read the issue before either sends its `PATCH`
- **THEN** the issue holds the marks of both writers after both operations complete

### Requirement: The repair stops after two rewrites
A record write operation SHALL attempt at most two rewrites after the initial `PATCH`.

#### Scenario: A third miss raises an error
- **WHEN** a mark remains missing after the second rewrite
- **THEN** the store raises `RoadmapRecordMarkLostError` naming the item number and the missing mark

### Requirement: Each repair is logged and counted
Each repaired mark write SHALL emit one log entry and increment the counter `devops_cli_roadmap_record_repairs_total`.

#### Scenario: One repaired write
- **WHEN** one write repairs a missing mark
- **THEN** the counter `devops_cli_roadmap_record_repairs_total` increases by 1 with labels `method` and `mark`

### Requirement: The repair counter is exported
The repair counter SHALL be registered in Prometheus metrics and exported via OTLP.

#### Scenario: Metrics inspection
- **WHEN** a repair occurs during a job execution
- **THEN** `/metrics` includes `devops_cli_roadmap_record_repairs_total`

### Requirement: A person's field change still raises
When a person changed a field label between the store's initial read and its write, the store SHALL raise `RoadmapItemChangedError` before sending any `PATCH`.

#### Scenario: Field modified before write
- **WHEN** a person alters an item field after the store read it
- **THEN** the store raises `RoadmapItemChangedError` and makes no update

### Requirement: Person edit outside record block is restored
When the text outside the record block changes between the read and the `PATCH`, the store SHALL restore the external text and increment `devops_cli_roadmap_record_lost_edit_total`.

#### Scenario: Body text updated concurrently
- **WHEN** a person modifies text outside the record block during an update
- **THEN** the store preserves the person's text and increments `devops_cli_roadmap_record_lost_edit_total` by 1
