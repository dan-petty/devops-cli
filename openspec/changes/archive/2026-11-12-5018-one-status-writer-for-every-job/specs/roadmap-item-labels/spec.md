## MODIFIED Requirements

### Requirement: The Service sets the Status from the job record
One function SHALL derive the Status of an item, in this order: New while it waits for refine, In Review while its pull request is ready, In Progress while a Job holds it or its pull request is open, Blocked while the record holds `implement.stopped`, Planned when its plan is on the default branch, else Ready. The sweep of the rows `implement`, `stage` and `stage_ready` SHALL write it only for an open item that holds Ready or Planned. Only a clear rule of the row `implement` SHALL end Blocked.

#### Scenario: A round from staging to a closed issue
- **WHEN** an item is staged, its plan is merged, a Job is made for it, the Job marks its pull request ready, and the issue closes
- **THEN** its label is `status/ready`, then `status/planned`, then `status/in-progress`, then `status/in-review` (set by the Job), and then none

#### Scenario: A drift
- **WHEN** an item holds `status/ready` that a job wrote and its plan is on the default branch
- **THEN** the next round of the row `implement` or `stage` replaces the label with `status/planned`

#### Scenario: A plan pull request that merged
- **WHEN** the row `stage_ready` reads the recorded stage pull request of a Ready item and it is merged
- **THEN** the item is Planned

#### Scenario: A stop on a Ready item
- **WHEN** an item holds `status/ready` that a job wrote and its record holds `implement.stopped`
- **THEN** the next sweep replaces the label with `status/blocked`

#### Scenario: An item in another Status
- **WHEN** an item is New, In Progress, In Review or Blocked
- **THEN** no sweep changes its label

#### Scenario: The order of the facts
- **WHEN** the facts say that the item waits for refine and that its pull request is ready for review, or that its pull request is ready for review and a Job holds it, or that its pull request is open and a stop is on record
- **THEN** the derived Status is New, In Review and In Progress, in that order

## ADDED Requirements

### Requirement: Every job writes the Status through one writer
Every job and command that sets the Status of an item SHALL write it through `write_status` of `src/devops_cli/roadmap/status_sync.py`. The writer SHALL derive the Status from the facts of its caller, SHALL write the label only when it differs, and SHALL read the issue again after the write. When the label is equal, it SHALL write only the marks and the body of its caller. A dry run SHALL send no request and SHALL return the would-be write.

#### Scenario: An equal label
- **WHEN** the writer gets facts whose Status is the label of the item
- **THEN** it sends no label write and no read

#### Scenario: A changed label
- **WHEN** the facts give another Status than the label of the item
- **THEN** the writer sends one label write and one read of the issue, and the label is the derived Status

#### Scenario: A dry run
- **WHEN** the writer runs as a dry run
- **THEN** it sends no request, and it returns the label of the item and the derived Status

### Requirement: A lost Status write fails
A label that is not the written Status when the writer reads the issue after its write SHALL raise `RoadmapStatusLostError` with the error code `ROADMAP_STATUS_LOST`. The dry-run plan of a job SHALL list that read after each Status write.

#### Scenario: A lost write
- **WHEN** another writer puts the old label back between the write and the read
- **THEN** the writer raises `RoadmapStatusLostError`, and its message names the item, the written Status and the label that the read found

### Requirement: No other module writes a Status label
No module of `src/devops_cli` other than `roadmap/status_sync.py` and the stores SHALL add or remove a Status label. A structural test SHALL hold this.

#### Scenario: A direct write
- **WHEN** another module calls `set_field` with `ItemField.STATUS`, or adds or removes a `status/` label
- **THEN** the structural test fails and names the file and the line
