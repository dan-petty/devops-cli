## ADDED Requirements

### Requirement: The review keeps its own listing snapshot
The project review SHALL write its listing snapshot to its own store under `review-listing` in the roadmap state directory, and SHALL NOT write the snapshot that intake keeps.

#### Scenario: A review writes the review snapshot
- **WHEN** a test runs one review over a 7-day window with an empty review store and an empty intake store
- **THEN** the review store holds one snapshot of the repository with the schema key of the release, and the intake store holds no file

#### Scenario: A review leaves the intake snapshot unchanged
- **WHEN** a test runs a review with an intake snapshot that holds a record of an older schema key
- **THEN** the intake snapshot file is byte-identical after the review, and the review store holds a new snapshot

### Requirement: The runs reader counts the runs of each status
The `github_runs` reader SHALL read the count of the Actions runs of a window with one GitHub request for each of the statuses success, failure, cancelled and in progress, and SHALL read the total count of the window with one more request. It SHALL NOT read a page of runs.

#### Scenario: A window of 2,072 runs
- **WHEN** the fake GitHub gives 1,927 successful, 29 failed, 104 cancelled and 12 in-progress runs and the total 2,072
- **THEN** the fact's value holds the four counts, its n is 2,072, and the reader counted 5 runs reads

#### Scenario: A window above the result cap
- **WHEN** the window holds more than 1,000 runs
- **THEN** the total count is exact and the reader sends 5 requests

#### Scenario: A run of another status
- **WHEN** the window holds 3 skipped runs
- **THEN** the total includes those 3 runs and the value holds no skipped key

### Requirement: A 7-day review sends at most 45 GitHub requests
A project review over a 7-day window MUST send at most 45 GitHub requests when it starts with no snapshot of any kind, and MUST send at most 45 when it starts with the review snapshot of an earlier review and no intake snapshot.

#### Scenario: A first 7-day review
- **WHEN** a test runs a review over a 7-day window with an empty review store and an empty intake store
- **THEN** the sum of the counts of the reads is at most 45

#### Scenario: A second 7-day review
- **WHEN** a test runs the review with the review snapshot of the previous review and no intake snapshot
- **THEN** the sum of the counts of the reads is at most 45 and the listing count is lower than the listing count of the first review

## MODIFIED Requirements

### Requirement: The listing reader fills the gap after the snapshot watermark
The `listing` reader SHALL read the review's own listing snapshot when its records have the schema of the release, and SHALL send only the issues and pull requests changed at or after the later of its watermark and the window start. With no such snapshot it SHALL read the intake snapshot that way, and with neither it SHALL read from the window start. It SHALL keep the merged records in the review's own store, and SHALL NOT write the intake snapshot.

#### Scenario: An issue after the watermark
- **WHEN** the review snapshot watermark is 2026-11-11T14:28:04Z, the window ends at 2026-11-11T14:51:23Z, and the fake GitHub gives one issue opened at 2026-11-11T14:40:00Z in the listing changed since the watermark
- **THEN** the fact of the issues opened in the window counts that issue once, the sent listing names since=2026-11-11T14:28:04Z, and the review snapshot holds that issue

#### Scenario: An old snapshot
- **WHEN** the review keeps no snapshot and the last full read of the intake snapshot is 3 days old
- **THEN** the fake GitHub records only the listing changed since its watermark, the intake snapshot file is byte-identical after the run, and the review snapshot holds the merged records

#### Scenario: No snapshot of this schema
- **WHEN** neither store holds a snapshot of this schema and the window starts at 2026-11-04T14:51:23Z
- **THEN** the fake GitHub records only the listing changed since 2026-11-04T14:51:23Z, and the review store holds a snapshot with the schema key of the release

#### Scenario: A watermark before the window start
- **WHEN** the review snapshot watermark is 3 weeks before the window start
- **THEN** each listing request names a since at or after the window start, and the listing count equals the listing count of a run with an empty review store

#### Scenario: A window wider than the review snapshot
- **WHEN** the window starts before the first window that the review snapshot covers
- **THEN** the fake GitHub records only the listing changed since the window start, and the review store holds a snapshot that covers the new window

## REMOVED Requirements

### Requirement: The runs reader splits a slice that reaches the result cap
**Reason**: The review reads the count of each status with one request, so it reads no page of runs and splits no slice; the result cap no longer applies.
**Migration**: The runs reader counts the runs of each status
