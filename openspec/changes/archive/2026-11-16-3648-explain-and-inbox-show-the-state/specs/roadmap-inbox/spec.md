## ADDED Requirements

### Requirement: The inbox line names the class and the action left of a stop
The line that `devops roadmap inbox` prints for a stopped item SHALL name the class of the failure and the action left, from the job record that the listing read.

#### Scenario: A blocked item with a class and an action left
- **WHEN** An open item holds `status/blocked` and a job record with `implement.stopped`, `implement.failure` and `implement.left_action`.
- **THEN** The subject of the line names the class, and the clear of the line names the action left beside the retry comment.

### Requirement: The inbox line states the attempts of a stopped step
The line of a stopped item SHALL state the number of attempts of the stopped step when `implement.trace` holds more than one, and SHALL state no number for one attempt.

#### Scenario: Two attempts of the stopped step
- **WHEN** The trace of a stopped item holds two attempt events of the stopped step, and the trace of a second stopped item holds one.
- **THEN** The subject of the first line states the count of 2, and the subject of the second line states no count.

### Requirement: The inbox line of a stop with no class on record
The line of a stopped item whose record holds no `implement.failure` SHALL name the step and the retry comment, and SHALL state that the record holds no class.

#### Scenario: A stop from an earlier runner image
- **WHEN** The job record of a blocked item holds `implement.stopped` and no `implement.failure`.
- **THEN** The line of `devops roadmap inbox` names the step and the retry comment, and it states that the record holds no class.

### Requirement: The inbox line of a stop adds no read
`devops roadmap inbox` SHALL build the line of a stopped item from the job record that the listing read, and MUST send no request for it.

#### Scenario: A repository that holds one stopped item
- **WHEN** The inbox reads a repository whose one open Item holds `status/blocked`, a Priority, and a job record with `implement.stopped`, `implement.failure` and `implement.left_action`, and a second repository whose one open Item holds `status/blocked` and a Priority and no stop.
- **THEN** The paths of the requests that each run sends are the same, and no request reads one issue.
