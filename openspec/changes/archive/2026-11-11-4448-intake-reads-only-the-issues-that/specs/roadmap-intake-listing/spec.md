## Purpose

The snapshot of the issue listing that `devops roadmap intake` keeps between runs, so that a run reads and parses only the issues that changed since the last run, and GitHub stays the source of truth.

## ADDED Requirements

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
Intake SHALL read the whole listing and replace the snapshot when no snapshot is kept, when it cannot be read, when another version of devops-cli wrote it, when its last full read is 24 hours old or older, and on `--full`. A snapshot that cannot be read SHALL give a warning that names its file.

#### Scenario: First run
- **WHEN** No snapshot is kept for the repository
- **THEN** The request holds no `since` parameter, and the run keeps a snapshot with every issue of the listing

#### Scenario: The flag, another version or an old full read
- **WHEN** A snapshot is kept and the run has `--full`, or another version wrote the snapshot, or its last full read is 25 hours old
- **THEN** The request holds no `since` parameter, and the new snapshot replaces the old one

#### Scenario: A snapshot that cannot be read
- **WHEN** The snapshot file holds no valid JSON
- **THEN** The run logs a warning that names the file, reads the whole listing and keeps a new snapshot

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
