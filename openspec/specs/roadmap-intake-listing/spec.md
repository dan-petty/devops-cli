# roadmap-intake-listing Specification

## Purpose
The snapshot of the issue listing that intake keeps between runs, in `devops roadmap intake` and in the Service, so that a run reads and parses only the issues that changed since the last run, and GitHub stays the source of truth.

## Requirements

### Requirement: Incremental listing read
With a snapshot that it can read from, intake SHALL read the issue listing with `state=all`, `sort=updated`, `direction=desc` and the watermark of the snapshot in `since`. Each issue of the read SHALL replace its record, and every other record SHALL come from the snapshot.

#### Scenario: A later run reads only the changed issues
- **WHEN** The snapshot holds 120 issues and GitHub lists 20 of them as changed since the watermark
- **THEN** The run sends one listing request with `since=<watermark>`, and it returns 120 issues, with the new title of each changed issue

#### Scenario: An unchanged issue is not read again
- **WHEN** GitHub lists issue 2 as changed and does not list issue 1
- **THEN** The record of issue 1 is the record that the snapshot holds

### Requirement: Watermark
Intake MUST store as the next watermark the earlier of the start of the read and the newest `updated_at` of the listing, less 60 seconds.

#### Scenario: An issue changed during the read
- **WHEN** The read starts at 10:00:00 and the newest `updated_at` is 10:00:30
- **THEN** The snapshot stores 09:59:00 as its watermark

#### Scenario: The local clock is ahead of GitHub
- **WHEN** The read starts at 10:10:00 and the newest `updated_at` is 10:00:00
- **THEN** The snapshot stores 09:59:00 as its watermark

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

### Requirement: Sub-issue count
When a changed issue joined or left a parent that the read did not return, intake SHALL move the sub-issue count of that parent by one.

#### Scenario: A sub-issue joins one parent and leaves another
- **WHEN** Issue 11 joins parent 10, which has 2 sub-issues, and issue 13 leaves parent 12, which has 1
- **THEN** Parent 10 has 3 sub-issues and parent 12 has 0

### Requirement: Atomic snapshot write
Intake SHALL write the snapshot through a temporary file and a rename in its directory. A failed write SHALL keep the earlier snapshot and log a warning that names the file.

#### Scenario: A failed write keeps the old snapshot
- **WHEN** The directory of the snapshot refuses the write
- **THEN** The old snapshot file is unchanged, the run logs a warning that names it, and the run returns the issues it read

### Requirement: Dry run names both reads
`devops roadmap intake --dry-run` SHALL list the read of the changed issues and the full read, each with the condition that selects it. With `--full`, it SHALL list only the full read.

#### Scenario: The dry run without and with --full
- **WHEN** A dry run is planned without `--full`, and again with it
- **THEN** The first plan lists the changed read before the full read, and the second lists only the full read

### Requirement: Repository name stays in the snapshot directory
The file store SHALL refuse a repository name that holds a `..` segment.

#### Scenario: A name that climbs out
- **WHEN** The file of the repository `../outside` is asked for
- **THEN** The store raises `SecurityError`

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

### Requirement: Schema key of the snapshot
The snapshot SHALL hold as its schema key the first 16 hex characters of the sha256 of the JSON schema of `IssueRecord`, and not the version of devops-cli.

#### Scenario: A release that keeps the record schema
- **WHEN** devops-cli 1.0.0 kept the snapshot, and devops-cli 2.0.0 with the same `IssueRecord` reads it
- **THEN** The run sends one listing request with `since=<watermark>`

### Requirement: A number that is no issue of the repository leaves the listing
When GitHub answers a read of a number with status 404 or with an answer that names another issue, the store SHALL take the record of that number out of its listing. When the listing of the store held the record, `IncrementalListing` SHALL leave the record out of each later read of the repository and out of the snapshot that the read keeps.

#### Scenario: A round drops the record of a redirected read
- **WHEN** the snapshot of a lane holds the open items 7 and 8, GitHub does not list issue 7 as changed and answers the read of issue 7 with issue 12 of another repository, and a round of the lane reads item 7 by its number
- **THEN** the read returns None, the store of that round lists item 8 only, the store of the next round lists item 8 only, and the snapshot that the next round keeps holds issue 8 only

#### Scenario: A read with status 404
- **WHEN** the snapshot of a lane holds the open items 7 and 8, and GitHub answers the read of issue 7 with status 404
- **THEN** the read returns None, and the store of that round and of the next round lists item 8 only

### Requirement: A dropped number stays out until GitHub lists it
`IncrementalListing` SHALL leave out the record of a dropped number whichever copy of the snapshot a read starts from. The number SHALL stay out until GitHub lists it as changed or until the next full read.

#### Scenario: Another copy of the snapshot holds the record
- **WHEN** a round of a lane dropped the record of issue 7, and the snapshot store then gives a copy that holds issue 7 again
- **THEN** the store of the next round of that lane lists item 8 only

#### Scenario: GitHub lists the number again
- **WHEN** a round of a lane dropped the record of issue 7, and GitHub then lists issue 7 as changed since the watermark
- **THEN** the store of the next round lists the items 7 and 8

### Requirement: A delivery that says that an issue left drops its record in each lane
A trigger of a delivery `issues` with the action `transferred` or `deleted` SHALL put the number of its issue in `TriggerBatch.left` of each lane that it wakes. A trigger of another event or action SHALL NOT. The round of a lane SHALL drop the record of each number of `TriggerBatch.left` from the listing of the lane before any row runs, with no GitHub read of that number, and SHALL log one warning for it.

#### Scenario: A batch names the numbers that left
- **WHEN** a lane worker gets the triggers `issues` `transferred` for 12, `issues` `labeled` for 14, `issues` `deleted` for 15 and `pull_request` `deleted` for 16 before a round
- **THEN** the batch of the round holds the subjects 12, 14, 15 and 16 and the left numbers 12 and 15, and the batch of a later trigger `issues` `edited` for 12 holds no left number

#### Scenario: The round of a lane drops the record
- **WHEN** the snapshot of a lane holds the open item 7, GitHub lists issue 7 no more, and `service_job` runs with a batch whose `left` holds 7
- **THEN** the store of the next round does not list item 7, the fake GitHub holds no request of `repos/acme/widgets/issues/7`, and the log holds the one line `#7 is no issue of acme/widgets now: a delivery says that it left. The lane status leaves it out.`

#### Scenario: A batch of another delivery drops nothing
- **WHEN** `service_job` runs with a batch of a delivery `issues` `labeled` for the subject 7
- **THEN** the store of the next round lists item 7
