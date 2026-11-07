# roadmap-intake-failures Specification

## Purpose
What `devops roadmap intake` shows when the write of a candidate fails: the class of the error and its masked reason, with the other candidates still written.

## Requirements

### Requirement: The failure line names the reason
The failure text of an intake round SHALL name, for each skipped candidate, the class of the error and the masked text of the failed write, bounded to `CONST_MAX_ERROR_DETAIL_LENGTH` characters.

#### Scenario: A candidate write fails with a GitHub error
- **WHEN** A test makes the write of one candidate raise `GitHubOperationError` with the text `HTTP 502: Bad Gateway`.
- **THEN** The intake failure text names the candidate with `GitHubOperationError: HTTP 502: Bad Gateway`.

### Requirement: The failure line holds no token
The failure text of an intake round MUST NOT contain a token that the error text holds.

#### Scenario: The error text holds a token
- **WHEN** A test makes the write error text contain a GitHub token.
- **THEN** The intake failure text does not contain the token.

### Requirement: The other candidates are written
Intake SHALL write the other candidates after the write of one candidate fails, and SHALL report the failed candidate.

#### Scenario: One candidate fails
- **WHEN** A test makes the write of the second of three candidates raise `GitHubOperationError`.
- **THEN** The first and the third candidate are written, and the run reports the second candidate as failed.
