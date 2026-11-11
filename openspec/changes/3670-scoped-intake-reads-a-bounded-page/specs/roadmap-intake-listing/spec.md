## ADDED Requirements

### Requirement: The Service reads through the snapshot
The intake rounds of the triage lane and the scoped intake of each delivery SHALL read every issue through the snapshot that the Service keeps in `listing` of its state directory. The status and model lanes SHALL read the whole listing.

#### Scenario: A scoped intake with a kept snapshot
- **WHEN** The Service keeps a snapshot of 250 items, and a delivery says that issue 251 opened
- **THEN** The scoped intake sends one listing request, with `since=<watermark>`, and places issue 251

#### Scenario: The store of each lane
- **WHEN** The status, triage and model lanes each open their store for a poll
- **THEN** Only the store of the triage lane reads through the snapshot in `listing` of the state directory

### Requirement: Schema key of the snapshot
The snapshot SHALL hold as its schema key the first 16 hex characters of the sha256 of the JSON schema of `IssueRecord`, and not the version of devops-cli.

#### Scenario: A release that keeps the record schema
- **WHEN** devops-cli 1.0.0 kept the snapshot, and devops-cli 2.0.0 with the same `IssueRecord` reads it
- **THEN** The run sends one listing request with `since=<watermark>`

## MODIFIED Requirements

### Requirement: Full read
Intake SHALL read the whole listing and replace the snapshot when no snapshot is kept, when it cannot be read, when its schema key is not the key of the current `IssueRecord` schema, when its last full read is 24 hours old or older, and on `--full`. A snapshot that cannot be read SHALL give a warning that names its file.

#### Scenario: First run
- **WHEN** No snapshot is kept for the repository
- **THEN** The request holds no `since` parameter, and the run keeps a snapshot with every issue of the listing

#### Scenario: The flag, another version or an old full read
- **WHEN** A snapshot is kept and the run has `--full`, or the snapshot holds the schema key of another version of `IssueRecord`, or its last full read is 25 hours old
- **THEN** The request holds no `since` parameter, and the new snapshot replaces the old one

#### Scenario: A snapshot that cannot be read
- **WHEN** The snapshot file holds no valid JSON
- **THEN** The run logs a warning that names the file, reads the whole listing and keeps a new snapshot
