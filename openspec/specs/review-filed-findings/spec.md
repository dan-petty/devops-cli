# review-filed-findings Specification

## Purpose
The marker that an issue filed from a review finding carries, the lookup that reads which findings issues already carry, and which findings the review leaves out of a hand-off to roadmap intake because an issue already carries them.

## Requirements

### Requirement: An issue filed from a review finding carries its fingerprint
The marker of a finding SHALL be `<!-- devops-review-finding: fingerprint_v2=<fingerprint> -->`, where the fingerprint is the finding's 64-character fingerprint v2 in lowercase hex. Reading a body SHALL give every fingerprint that a marker in it names. A value that is not such a fingerprint SHALL be refused with a `ValidationError`.

#### Scenario: A marker round-trips its fingerprint
- **WHEN** a body holds text, the marker of one fingerprint, more text, and the marker of a second fingerprint
- **THEN** reading the body gives both fingerprints

#### Scenario: A value that is no fingerprint
- **WHEN** a marker is asked for a value that is not 64 lowercase hex characters
- **THEN** it is refused with a `ValidationError`

### Requirement: The lookup reads the marked issues with one issue search
The lookup SHALL read the issues of the repository, open and closed, whose body holds `devops-review-finding`, with GitHub's issue search through the GitHub session, 100 issues a page. It SHALL fail with `GitHubUnreadError` when a page is marked incomplete or the search has more results than GitHub returns.

#### Scenario: Two pages of marked issues
- **WHEN** the search reports 101 results, 100 on its first page and 1 on its second
- **THEN** the lookup reads both pages and knows the fingerprints of all 101 issues

#### Scenario: An incomplete search
- **WHEN** GitHub marks a page of the search `incomplete_results`
- **THEN** the lookup fails with `GitHubUnreadError`

### Requirement: The review leaves out a finding that an issue settles
A finding SHALL be left out when an issue that carries its fingerprint is open, closed as not planned, or closed as a duplicate. A finding whose only issues were closed as completed, and a finding that no issue carries, SHALL stay.

#### Scenario: Issues in each state
- **WHEN** an open issue carries finding A, an issue closed as not planned carries B, an issue closed as a duplicate carries D, an issue closed as completed carries C, and no issue carries E
- **THEN** the findings that stay are C and E, in their order

#### Scenario: A completed issue and an open issue carry one finding
- **WHEN** an issue closed as completed and an open issue both carry finding A
- **THEN** finding A is left out

### Requirement: A dry run of the lookup makes no request
With a dry run, the lookup SHALL make no request and SHALL return the search that a real run sends, and it SHALL leave out no finding.

#### Scenario: The dry run of the lookup
- **WHEN** the lookup runs as a dry run
- **THEN** GitHub receives no request, the lookup names one planned search for the marker's phrase, and every finding stays
