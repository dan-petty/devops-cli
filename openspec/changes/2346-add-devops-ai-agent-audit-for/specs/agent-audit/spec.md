## Purpose
Counts the recurring problems of agent sessions on one host from their signatures, keeps only masked signatures and pointers, and turns the findings into roadmap candidates.

## ADDED Requirements

### Requirement: Cross-session failure count
The audit SHALL report a failing signature that occurs in three sessions as one finding with a count of 3.

#### Scenario: Same failure in three sessions
- **WHEN** The audit reads three fixture transcripts that each hold the same failing command with the same exit status and first error line.
- **THEN** The report holds one finding for that signature, the count is 3, and the finding holds three pointers, one for each session file.

### Requirement: Secret masking in report and store
The audit SHALL mask every secret in a kept line before it writes the report or the stored counts.

#### Scenario: GitHub token in a transcript line
- **WHEN** A fixture transcript line holds a `ghp_` token.
- **THEN** The report and the stored counts file hold `<masked-github-token>` and no `ghp_` token.

### Requirement: Unknown record type
The audit MUST continue when it reads a record type that the parser does not know.

#### Scenario: Unknown record type before a known record
- **WHEN** A fixture transcript holds a record of type `api-request-blob` before a record of a known type.
- **THEN** The run exits 0 and the report holds the finding from the known record.

### Requirement: Idempotent stored counts
The audit SHALL keep each signature's count unchanged when a second run reads the same session and line.

#### Scenario: Second run over the same files
- **WHEN** Two runs read the same fixture files on the same date.
- **THEN** The stored counts file holds the same count for each signature after each run.

### Requirement: Warning named by an open issue
The audit SHALL NOT report a `devops` warning as a new finding when an open issue names that warning.

#### Scenario: Warning named by an open issue
- **WHEN** A fixture warning matches the title or body of an open issue that the stub GitHub client returns.
- **THEN** The warning is absent from the new findings and the report marks it as tracked.

### Requirement: Dry run makes no request
A run with `--dry-run` MUST make no request to a model or to GitHub and MUST read no file outside the named source.

#### Scenario: Dry run over a fixture
- **WHEN** The audit runs with `--dry-run` over a fixture directory.
- **THEN** The stub clients record no call and every opened path is under the fixture directory.

### Requirement: Refused flag pair
The command MUST refuse a run that holds both `--dry-run` and `--confirm`.

#### Scenario: Dry run with confirm
- **WHEN** The audit runs with `--dry-run` and `--confirm`.
- **THEN** The command exits with a usage error and files no issue.

### Requirement: Model stage grouping
The model stage SHALL send only masked signatures to one `devops ai` model and SHALL attach the returned groups to the findings.

#### Scenario: Grouping with a stub model
- **WHEN** The audit runs with a stub model client that records its request.
- **THEN** The request holds no raw transcript line and the report holds the group that the stub returns.

### Requirement: Ranking by sessions
The audit SHALL rank a finding with more sessions above a finding with fewer sessions.

#### Scenario: Two signatures with different session counts
- **WHEN** A fixture holds signature A in three sessions and signature B in one session.
- **THEN** Signature A comes before signature B in the report.

### Requirement: Default source
The audit SHALL read only Claude Code transcripts when the run names no `--source`.

#### Scenario: No source flag
- **WHEN** The audit runs over a fixture directory with no `--source` flag and a shell-history fixture sits beside the transcripts.
- **THEN** The report holds the transcript finding and the shell-history fixture is never opened.

#### Scenario: The shell source
- **WHEN** The audit runs with `--source shell` over a fixture directory that holds a shell-history file and a transcript.
- **THEN** The report holds the shell-history finding and no transcript file is opened.

### Requirement: Confirm files each draft through intake
A run with `--confirm` SHALL file each drafted group as a candidate through `devops roadmap intake --confirm`.

#### Scenario: Confirm files the drafts
- **WHEN** The audit runs with `--confirm` and a stub intake runner.
- **THEN** The run starts one intake process for each drafted group, and the report lists the number of each filed candidate.
