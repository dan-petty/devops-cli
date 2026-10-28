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

### Requirement: The hand-off takes the open tool findings of a session
A finding of findings.json SHALL qualify for the hand-off when its fingerprint is a fingerprint v2 (64 lowercase hex characters) and its verdict is neither INVALIDATED nor MITIGATED.

#### Scenario: Findings with each verdict
- **WHEN** a session holds findings with a fingerprint v2 and the verdicts VERIFIED, UNVERIFIED, INVALIDATED and MITIGATED, and a VERIFIED finding whose fingerprint is not a fingerprint v2
- **THEN** only the VERIFIED and the UNVERIFIED findings with a fingerprint v2 qualify, in their order

### Requirement: The candidate of a finding cites it and carries its marker
The candidate of a qualifying finding SHALL have the title `fix: <finding title> (<location>)`, filed by an agent. Its body SHALL name the session, the location, the tool, the severity and the verdict, and hold the description, the cited code, the fix and the verification criteria that the finding has. The body SHALL end with the marker of the finding's fingerprint v2.

#### Scenario: A verified ruff finding
- **WHEN** the candidate is made for a VERIFIED ruff finding at `src/app.py:3` of session `20261028-120000`
- **THEN** its title is `fix: <finding title> (src/app.py:3)`, its body names the session, the location, `ruff`, the severity and VERIFIED, and its last line is the finding's marker

### Requirement: `devops review intake` hands the findings that no issue settles to intake
`devops review intake [SESSION]` SHALL hand each qualifying finding of a session on merged code that no issue settles to roadmap intake, as one candidate, in the order of findings.json. With `--confirm` it SHALL file and place each candidate. With `--plan`, or with no mode flag, it SHALL write nothing. More than one mode flag SHALL be refused.

#### Scenario: One finding is filed and one is already carried
- **WHEN** the hand-off runs with confirm for a session on merged code with qualifying findings A and B, and an open issue carries the marker of A
- **THEN** intake files one issue, for B, whose body ends with the marker of B, and the model is called one time

#### Scenario: A plan writes nothing
- **WHEN** the hand-off runs without confirm for the same session
- **THEN** no issue is filed, and the plan holds one decision, for B

#### Scenario: Every qualifying finding is already filed
- **WHEN** `devops review intake --plan` runs for a session whose qualifying findings an open issue carries
- **THEN** the command builds no model, files nothing, says that no finding is left to hand off, and exits 0

### Requirement: A session that is not on merged code is refused
`devops review intake` SHALL refuse a session that is not on merged code with `ReviewHandOffRefusedError`, exit code 1 and the reason, before it sends any request or calls a model.

#### Scenario: A session of a tree with a change
- **WHEN** `devops review intake` runs for a `path` session of a dirty tree
- **THEN** it exits 1, names the changed tree, and GitHub receives no request

### Requirement: A candidate that looks like it holds a secret is refused
`devops review intake` SHALL refuse a session whose candidate text looks like it holds a secret, and name the finding, before it sends any request or calls a model.

#### Scenario: A finding that quotes a token
- **WHEN** a qualifying finding's description holds a GitHub token
- **THEN** the hand-off raises `SecurityError` naming the finding's location, and GitHub receives no request

### Requirement: A dry run of the hand-off makes no request
`devops review intake --dry-run` SHALL make no request and call no model. It SHALL print each candidate's title, the issue search, and the requests that intake makes for the first candidate.

#### Scenario: The dry run of a session with two qualifying findings
- **WHEN** `devops review intake --dry-run` runs for a session on merged code with two qualifying findings
- **THEN** GitHub receives no request, and the output holds both titles, the issue search and intake's model call for the first candidate
