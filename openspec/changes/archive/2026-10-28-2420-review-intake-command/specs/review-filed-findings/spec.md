## ADDED Requirements

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
