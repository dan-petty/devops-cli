## MODIFIED Requirements

### Requirement: Full read
Intake SHALL read the whole listing and replace the snapshot when neither the local file nor the shared tier of `valkey-devops` keeps a fit snapshot of the repository, and on `--full`. A snapshot is fit when it can be read, its schema key is the key of the current `IssueRecord` schema, and its last full read is younger than 24 hours. The shared tier keeps no snapshot of a private repository. A local snapshot file that cannot be read SHALL give a warning that names its file.

#### Scenario: First run
- **WHEN** No snapshot is kept for the repository in the local file or in the shared tier
- **THEN** The request holds no `since` parameter, and the run keeps a snapshot with every issue of the listing

#### Scenario: The flag, another version or an old full read
- **WHEN** A snapshot is kept and the run has `--full`, or each kept snapshot holds the schema key of another version of `IssueRecord`, or the last full read of each kept snapshot is 25 hours old
- **THEN** The request holds no `since` parameter, and the new snapshot replaces the old one

#### Scenario: A snapshot that cannot be read
- **WHEN** The snapshot file holds no valid JSON, and the shared tier keeps no fit snapshot of the repository
- **THEN** The run logs a warning that names the file, reads the whole listing and keeps a new snapshot

#### Scenario: A fit shared snapshot and no local file
- **WHEN** No local snapshot is kept, and the shared tier keeps a fit snapshot of the public repository
- **THEN** The run sends the listing requests with `since=<watermark>` of the shared snapshot, and keeps a local snapshot with every issue

### Requirement: The Service reads through the snapshot
The rounds of the lane that holds `intake` and the scoped intake of each delivery SHALL read every issue through the snapshot that the Service keeps in `listing` of its state directory. Each other lane SHALL read every issue through its own snapshot in `listing-<lane>` of the state directory. Each of these snapshot files SHALL sit under the shared tier of `valkey-devops`, and a read SHALL start from the fit copy with the newer watermark of the two.

#### Scenario: A scoped intake with a kept snapshot
- **WHEN** The Service keeps a snapshot of 250 items, and a delivery says that issue 251 opened
- **THEN** The scoped intake sends one listing request, with `since=<watermark>`, and places issue 251

#### Scenario: The store of each lane
- **WHEN** The lanes `metrics`, `intake` and `refine` each open their store for a poll
- **THEN** The store of `metrics` reads through the snapshot in `listing-metrics`, the store of `intake` through the snapshot in `listing`, and the store of `refine` through the snapshot in `listing-refine`, each under the shared tier

#### Scenario: A status round with a kept snapshot
- **WHEN** The lane `stage_ready` ran one round, and a second round is due
- **THEN** The second round sends one listing request, with `since=<watermark>`

#### Scenario: The newer copy of the two tiers
- **WHEN** The snapshot file of a lane has the watermark 09:00, and the shared tier keeps a fit snapshot of the public repository with the watermark 10:00
- **THEN** The round sends the listing request with `since=` the watermark 10:00
