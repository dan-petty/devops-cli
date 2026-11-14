## ADDED Requirements

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
