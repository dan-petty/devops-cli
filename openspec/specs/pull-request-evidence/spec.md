# pull-request-evidence Specification

## Purpose
Formats and posts pull request check runs and fail-to-pass test results as a sticky pull request comment.

## Requirements

### Requirement: devops pr evidence posts the check results of the head commit
The `devops pr evidence` command SHALL read the check runs of the pull request head commit from GitHub and SHALL post them in one comment on the pull request.

#### Scenario: Reads checks for the head commit
- **WHEN** A test runs `devops pr evidence 42` against a recorded pull request with one head commit and two check runs.
- **THEN** The command requests the check runs for that head commit SHA and builds a table with both check runs.

#### Scenario: Builds the comment text
- **WHEN** The recorded head commit has a passing check and a skipped check, and the pull request is a fix with a fail-to-pass check run.
- **THEN** The comment names the head commit, lists each check with its conclusion and link, links the fail-to-pass run, and names the skipped check on its own line.

#### Scenario: Omits fail-to-pass for a non-fix
- **WHEN** A test runs the command for a pull request with a feat title and no fail-to-pass check run.
- **THEN** The comment text has no fail-to-pass section and no fail-to-pass link.

### Requirement: devops pr evidence keeps one comment per pull request
The command SHALL keep one comment by a marker line and matching author identity, SHALL update that comment on a new head, and MUST never post a second comment.

#### Scenario: Updates the marked comment
- **WHEN** A test runs the command twice and the recorded issue comments hold one comment with the marker line and matching author.
- **THEN** The second run sends one PATCH request for the marked comment and no POST request for a new comment.

#### Scenario: Posts one comment when none carries the marker
- **WHEN** A test runs the command against a recorded pull request whose issue comments hold no marker line.
- **THEN** The command sends one POST request and no PATCH request.

### Requirement: devops pr evidence takes no free text
The command MUST take no free text. Every number in the comment MUST come from the check runs that GitHub returns.

#### Scenario: Rejects free text
- **WHEN** A test runs `devops pr evidence 42 --body '3 passed'`.
- **THEN** The command exits with a usage error and sends no request.

### Requirement: devops pr evidence accepts an attribution footer
When `--attribution` is given, the command SHALL append the attribution text to the comment footer.

#### Scenario: Ends with footer
- **WHEN** A test runs the command with `--attribution` and a recorded pull request.
- **THEN** The comment text ends with the attribution footer.
