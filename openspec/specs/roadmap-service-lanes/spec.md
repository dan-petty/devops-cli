# roadmap-service-lanes Specification

## Purpose
The lanes of the roadmap Service: one worker and one trigger queue for each lane and repository, one lane for each row of the due table by default, the setting `service.lanes` that groups rows, the clone and the listing snapshot of each lane, and the subject that a trigger carries.

## Requirements

### Requirement: Each row runs in a lane of its own
`service_jobs` SHALL give each row of `DEFAULT_DUE_TABLE` a lane of its own when `service.lanes` is empty, and the name of the lane SHALL be the name of the row. The Service SHALL run one worker with one trigger queue for each lane and repository.

#### Scenario: The default lanes
- **WHEN** `service_jobs` builds the lanes with no setting
- **THEN** the names of the lanes are the names of the rows of `DEFAULT_DUE_TABLE`, in the order of the table, and each lane holds its one row

#### Scenario: One worker for each lane and repository
- **WHEN** the Service starts with two repositories and the default lanes
- **THEN** it has one worker for each pair of a repository and a lane

### Requirement: A round of one lane does not wait for a round of another lane
A round of one lane SHALL NOT wait for a round of another lane of the same repository.

#### Scenario: A blocked stage round
- **WHEN** a stage round of a repository blocks, and a poll makes `refine` due for the same repository
- **THEN** a refine round of that repository runs and ends while the stage round still runs

### Requirement: The setting service.lanes groups rows into a lane
The setting `service.lanes` SHALL map a lane name to the rows that the lane runs. A row that no lane names SHALL keep a lane of its own. The rows of a lane SHALL run in the order of `DEFAULT_DUE_TABLE`. The Service SHALL read the setting when it starts. The setting SHALL refuse a name that is not a lowercase name, a lane with no row, and a row in two lanes. `service_lanes` SHALL raise `ConfigurationError` for an unknown row, and for a lane name that is the name of a row in another lane.

#### Scenario: Two rows in one lane
- **WHEN** `service.lanes` is `{model: [refine, stage]}`
- **THEN** the lane `model` holds `stage` and then `refine`, and each other row has a lane of its own

#### Scenario: A row in two lanes
- **WHEN** `service.lanes` is `{a: [stage], b: [stage, refine]}`
- **THEN** the settings refuse the value and name the row `stage`

#### Scenario: An unknown row
- **WHEN** `service.lanes` is `{model: [plan]}`
- **THEN** `service_lanes` raises `ConfigurationError` that names the row `plan` and the field `service.lanes`

#### Scenario: A lane name of another row
- **WHEN** `service.lanes` is `{stage: [refine]}`
- **THEN** `service_lanes` raises `ConfigurationError` that names the lane `stage`

### Requirement: Each lane works in a clone of its own
Each lane SHALL run its rows that need files in the clone `lanes/<lane>` of the repository directory, which `ensure_checkout` makes and updates. No two lanes SHALL use the same clone.

#### Scenario: Two lanes and their clones
- **WHEN** the lanes `stage` and `refine` of a repository each run a round with a row that needs files
- **THEN** the row `stage` gets the clone `lanes/stage` and the row `refine` the clone `lanes/refine`, each at the tip of the default branch of origin

#### Scenario: A change in the clone of one lane stays
- **WHEN** a file of the clone of the lane `stage` changes, and the lane `refine` then runs a round
- **THEN** the file of the clone of `stage` keeps the change

### Requirement: The start removes the state of lanes that the Service does not run
When `devops serve --service` starts, the Service SHALL remove each clone and each snapshot of a lane that it does not run: the clones under `lanes/` of each repository of `service.repos`, the clones `clone`, `model-clone` and `triage-clone`, and the directories `listing-<name>` of the state directory. It SHALL keep every other file. A path that it cannot remove SHALL go to the log as a warning, and the start SHALL go on.

#### Scenario: A clone and a snapshot of a lane that the Service does not run
- **WHEN** the repository directory holds `lanes/model`, `lanes/stage` and `model-clone`, and the state directory holds `listing-model`, `listing-stage` and `listing`, and the Service runs the default lanes
- **THEN** the start removes `lanes/model`, `model-clone` and `listing-model`, and keeps `lanes/stage`, `listing-stage`, `listing` and `schedule.json`

### Requirement: A trigger carries an optional subject
A trigger SHALL carry an optional subject, the number of the issue that its event is about. A batch SHALL hold the subjects of the triggers that it coalesces. The webhook consumer SHALL give the number of the issue of a delivery as the subject.

#### Scenario: Two triggers with subjects
- **WHEN** a lane of a repository gets a trigger with the subject 12 and a trigger with the subject 14 before its next round
- **THEN** the batch of the round holds the subjects 12 and 14

#### Scenario: A poll has no subject
- **WHEN** a lane gets only a poll trigger
- **THEN** the batch of the round holds no subject

### Requirement: The lanes of one poll share one read of the issue events
One poll of a repository SHALL read the issue-events listing once for all lanes that need it, through a cache that lives for that poll only. The cache SHALL keep the listing of each repository apart.

#### Scenario: Three lanes share one request
- **WHEN** a poll runs three lanes of one repository and each lane has a due row that reads issue events
- **THEN** the fake GitHub session records one request for `repos/<repo>/issues/events`

#### Scenario: A second poll sends a new request
- **WHEN** a second poll runs after the first poll has completed
- **THEN** the fake GitHub session records a new request for the issue-events listing

#### Scenario: Lanes with different cutoffs share one listing
- **WHEN** two lanes read one poll at different cutoffs and the earlier cutoff fills the cache first
- **THEN** the later lane receives every event at or after its own cutoff from the one cached listing

#### Scenario: Two repositories in one poll
- **WHEN** one poll reads issue events for two repositories
- **THEN** the fake GitHub session records one request for each repository's issue-events listing
