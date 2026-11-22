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
The `github_runs` reader SHALL count the Actions runs created after the window start, in whole seconds, up to the window end. It SHALL read the total of each slice first. It SHALL split a slice at the GitHub cap of 2,500 in two halves by created time. For each slice under the cap, it SHALL add the total and the count of each status: success, failure, cancelled and in progress. It SHALL raise an error for a page with no total, a one-second slice at the cap and status counts above a total.

#### Scenario: A window under the count cap
- **WHEN** the fake GitHub gives 1,927 successful, 29 failed, 104 cancelled and 12 in-progress runs in a 7-day window, 2,072 runs in all
- **THEN** the fact's value holds the four counts, its n is 2,072, and the review counts 5 reads of the `github_runs` reader

#### Scenario: A window above the count cap
- **WHEN** the window holds 4,500 runs and the fake GitHub stops each total at 2,500, as GitHub does
- **THEN** the reader splits the window in two halves, the counts of the halves add up to the counts of the 4,500 runs, and the reader sends 11 requests

#### Scenario: A one-second slice at the count cap
- **WHEN** one second holds 2,500 runs
- **THEN** the reader raises an error that names the cap of 2,500

#### Scenario: Status counts above the total
- **WHEN** the four status counts of a slice add up to 16 and its total is 10
- **THEN** the reader raises an error that names the sum 16

#### Scenario: A runs page with no total
- **WHEN** the fake GitHub gives a runs page with no `total_count`
- **THEN** the runs fact has the status `error` and no count of 0

#### Scenario: A run in the start second
- **WHEN** one run is created in the start second of the window and one run in its end second
- **THEN** the window counts only the run of its end second, and the window that ends at that start counts the other run

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
The `listing` reader SHALL read the review snapshot of the release schema, else the intake snapshot. It SHALL read the issues and pull requests changed from the later of the watermark and the window start. It SHALL read from the window start when no snapshot fits or the window starts before the first window that the review snapshot covers. It SHALL keep the merged records only in the review store. A read that starts after the watermark SHALL keep a snapshot of only the time from its start.

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

#### Scenario: A second review over a new window
- **WHEN** a second review reads a window one day after the window of the first review, and the new window holds the watermark that the first review kept
- **THEN** the fake GitHub records only the listing changed since that watermark: one page, where a review of the new window with an empty review store reads three

#### Scenario: A read that starts after the watermark
- **WHEN** review A keeps the watermark 2026-09-14T23:59:00Z, an issue closes on 2026-10-06, review B reads a window that starts on 2026-10-14, and review C reads a window that starts on 2026-09-21
- **THEN** review C sends the listing changed since 2026-09-21T00:00:00Z and gives the closed record of that issue

## REMOVED Requirements

### Requirement: The runs reader splits a slice that reaches the result cap
**Reason**: The review reads no page of runs, so the page cap of 1,000 no longer applies. It reads counts, and splits a slice at the count cap of 2,500.
**Migration**: The runs reader counts the runs of each status
