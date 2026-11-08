# roadmap-intake-failures Specification

## Purpose
What `devops roadmap intake` shows when the write of a candidate fails: the class of the error and its masked reason, with the other candidates still written.

## Requirements

### Requirement: The failure line names the reason
The failure text of an intake round SHALL name, for each skipped candidate, the class of the error and the masked text of the failed write, bounded to `CONST_MAX_ERROR_DETAIL_LENGTH` characters.

#### Scenario: A candidate write fails with a GitHub error
- **WHEN** A test makes the write of one candidate raise `GitHubOperationError` with the text `HTTP 502: Bad Gateway`.
- **THEN** The intake failure text names the candidate with `GitHubOperationError: HTTP 502: Bad Gateway`.

### Requirement: The failure line holds no token
The failure text of an intake round MUST NOT contain a token that the error text holds.

#### Scenario: The error text holds a token
- **WHEN** A test makes the write error text contain a GitHub token.
- **THEN** The intake failure text does not contain the token.

### Requirement: The other candidates are written
Intake SHALL write the other candidates after the write of one candidate fails, and SHALL report the failed candidate.

#### Scenario: One candidate fails
- **WHEN** A test makes the write of the second of three candidates raise `GitHubOperationError`.
- **THEN** The first and the third candidate are written, and the run reports the second candidate as failed.

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
