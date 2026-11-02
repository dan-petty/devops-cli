## ADDED Requirements

### Requirement: The metrics row sends the age of the oldest item in each state
For its repository, each round of the metrics row of the Service SHALL send `devops_cli_roadmap_item_age_seconds` and `devops_cli_roadmap_oldest_item_number` for each pair of a Status value and a `plan` flag, with the labels `repo`, `state` and `plan`. The age is the clock minus the time of the `labeled` event that set the current Status label of the oldest open Item of the pair. The number is the issue number of that Item. A pair with no Item sends 0 for both.

#### Scenario: The age comes from the label event and the clock
- **WHEN** an open Item got the label `status/ready` at time T, and the clock reads T plus 3600 seconds
- **THEN** the point with `state` `ready` has the age 3600 and the number of that Item

#### Scenario: The oldest Item of a pair
- **WHEN** two open Items got `status/ready` at T and at T plus 600 seconds, and the clock reads T plus 3600 seconds
- **THEN** the age of the pair is 3600 and its number is the number of the first Item

#### Scenario: A label that a person removed and added again
- **WHEN** an Item got `status/ready` at T, lost it at T plus 100 seconds, and got it again at T plus 200 seconds
- **THEN** the age counts from T plus 200 seconds

#### Scenario: The plan flag
- **WHEN** the job record of a Ready Item holds `stage.pr`, and the job record of another Ready Item holds none
- **THEN** the first sends `plan` `true` and the second sends `plan` `false`

#### Scenario: A pair with no Item
- **WHEN** no open Item is Blocked
- **THEN** the round sends the age 0 and the number 0 for `state` `blocked`, for both values of `plan`

### Requirement: The metrics row sends the age of the oldest claim
`devops_cli_roadmap_claim_age_seconds` SHALL carry the label `repo`. Its value SHALL be the clock minus the time of the `labeled` event of the current `owner/*` label of the open Item whose claim is oldest, and 0 when no open Item holds a claim.

#### Scenario: Two claims
- **WHEN** an Item got `owner/agent` at T and another got `owner/service` at T plus 600 seconds, and the clock reads T plus 3600 seconds
- **THEN** the claim age is 3600

### Requirement: The label events of an Item are read when its labels change
The metrics row SHALL read the label changes of an open Item that holds a Status or an Owner label at the first round of the process that sees its current Status and Owner labels. It SHALL NOT read them again while those labels stay the same.

#### Scenario: Two rounds with no change
- **WHEN** two rounds run over the same Items and labels
- **THEN** the second round sends no request to the events of an issue

#### Scenario: A Status that changed
- **WHEN** a person changes the Status label of one Item between two rounds
- **THEN** the second round reads the events of that issue only, and the age counts from the new event

### Requirement: A failed read of the label events keeps the other metrics
When the read of the label changes of an Item fails, `collect_project_metrics_report` SHALL log a warning, SHALL return the other sections of the report whole, and SHALL return no age. The row SHALL send no age point that round.

#### Scenario: GitHub answers HTTP 500 for an events listing
- **WHEN** GitHub answers HTTP 500 for `issues/<number>/events`
- **THEN** the round sends the item counts and the releases, no age point, and the log holds a warning that names the repository

### Requirement: A run from a person's login sends no age
`devops gh metrics --emit-telemetry` SHALL send none of the three roadmap age gauges, and SHALL send no request to the events of an issue.

#### Scenario: The command emits the report
- **WHEN** `devops gh metrics --emit-telemetry` runs and GitHub is faked at the `gh` edge
- **THEN** no age point is sent and no request path ends in `/events`

### Requirement: The dashboard shows the age of the oldest item in each state
The project dashboard SHALL hold the timeseries panel "Oldest Item Age by State" in the row of the items panels, with the unit `s`. Its queries SHALL be `max by (state) (last_over_time(devops_cli_roadmap_item_age_seconds[$__range]))` and `max(last_over_time(devops_cli_roadmap_claim_age_seconds[$__range]))`. It SHALL leave the right half of its row free.

#### Scenario: The queries of the panel
- **WHEN** a test reads the panel "Oldest Item Age by State" of `project-metrics.json`
- **THEN** its two queries are the ones above, each names a declared instrument, and no panel overlaps it
