## ADDED Requirements

### Requirement: An Item that a person changed is no failed placement
Intake SHALL NOT count a candidate as failed when the write of the candidate raises `RoadmapItemChangedError`. It MUST write the other candidates, log one INFO line that names the candidate, and end the round with no error. The candidate SHALL stay in the intake record and be decided again.

#### Scenario: A person changes one of three candidates
- **WHEN** A test makes the `set_field` write of the second of three candidates raise `RoadmapItemChangedError`.
- **THEN** The first and the third candidate are placed, the run reports no failed candidate, one INFO line names the second candidate, and the next plan holds the second candidate.

#### Scenario: A round ends with a changed candidate
- **WHEN** A test runs the intake job with the write of one of three candidates raising `RoadmapItemChangedError`.
- **THEN** The job returns with no error, and the intake record holds that candidate.

### Requirement: The refine stamp survives a failed placement
A round that places a critical fix or a P0 item SHALL write the `refine_due` stamp before it raises for the failed placement of another candidate. A round SHALL NOT write the stamp for a P0 decision whose own placement failed or was refused as changed.

#### Scenario: Another candidate fails
- **WHEN** A test places a P0 candidate in a round in which the label write of another candidate raises `GitHubOperationError`.
- **THEN** The round writes the `refine_due` stamp and then raises `RoadmapIntakeError`.

#### Scenario: The P0 candidate itself fails or changed
- **WHEN** A test makes the write of the P0 candidate raise `GitHubOperationError`, or `RoadmapItemChangedError`.
- **THEN** The round writes no `refine_due` stamp.
