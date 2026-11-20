# roadmap-intake-writes Specification

## Purpose
Intake places each candidate with the fewest GitHub writes that keep its labels and job record correct: one create request for a new candidate, and one batched field write for an existing one, with the Priority always last.

## Requirements

### Requirement: One request files a new candidate
Intake SHALL file a new candidate with its source, type, scope, Status, Value and Effort labels, and the job record of the three fields, in one `create_issue` request.

#### Scenario: Filed labels of a new candidate
- **WHEN** intake confirms a new candidate that has a parent and sets Status, Value and Effort
- **THEN** the store records one `create_issue` call whose labels hold the source, type, scope, Status, Value and Effort labels, and whose body holds the job record of the three fields

### Requirement: No separate label or field write of a new candidate
Intake MUST make no `label_issue` call and no `set_field` call for Status, Value or Effort of a new candidate.

#### Scenario: Writes of a new candidate
- **WHEN** intake confirms a new candidate that has a parent and sets Status, Value and Effort
- **THEN** the store records one `create_issue`, one `add_sub_issue`, one `comment` and one `set_field` for Priority, and no other write

### Requirement: Priority last
Intake MUST set Priority with one `set_field` after the create request, the sub-issue link and the comment.

#### Scenario: Order of the writes
- **WHEN** intake confirms a new candidate that has a parent
- **THEN** the Priority `set_field` is the last write that the store records

### Requirement: Fields of an existing issue in one write
The store SHALL write Status, Value and Effort of an existing issue with one read of the issue and one `PATCH`, which also carries the job record.

#### Scenario: Writes of an existing candidate
- **WHEN** intake places an existing candidate that sets Status, Value and Effort
- **THEN** the store records one read of the issue and one `PATCH` that carries the three labels and the job record

### Requirement: A person's label stays
The batched field write MUST refuse the write when a person changed one of the fields since the store read the issue.

#### Scenario: A person changed a field
- **WHEN** a person changes the Value label of the issue after the read and before the batched write
- **THEN** the store raises `RoadmapItemChangedError` and writes no field

### Requirement: Dry run shows one create request
The dry-run write plan MUST list one create request that carries every label of a new candidate and no separate label or field write but the Priority one.

#### Scenario: Dry-run writes of a new candidate
- **WHEN** a person runs `devops roadmap intake --dry-run` for a new candidate
- **THEN** the write plan holds one create request with every label, then the sub-issue link, the comment and the Priority write

### Requirement: The filed body names its source under its own heading
Intake SHALL file the source of a candidate as the line `Source: <source>` under a `## Source` heading after the body of the candidate. It SHALL write no source line inside a Dependencies section of level 2 or lower, and the source line SHALL name no blocker inside a level-1 Dependencies section, so that the source names no dependency. A retry of a new candidate SHALL find an issue whose body has the form from before this rule, which ends with the line `Source: <source>` and no heading.

#### Scenario: A filed candidate with a source
- **WHEN** `NewCandidate.filed_body` builds the body of a candidate whose body ends with a level-1 `# Dependencies` section and whose source is `#4989`
- **THEN** the body ends with the `## Source` heading and the line `Source: #4989`, and `body_dependencies` of that body returns an empty list

#### Scenario: A retry finds an issue of the old form
- **WHEN** a run before this rule filed a candidate with a source, with the body that ends with the line `Source: <source>`, and stopped before Priority, and intake runs again for the same candidate
- **THEN** intake finds that issue and files no second issue
