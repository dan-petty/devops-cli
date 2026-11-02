## ADDED Requirements

### Requirement: devops pr evidence posts the check results of the head commit
The `devops pr evidence` command SHALL read the check runs of the pull request head commit from GitHub and SHALL write them in one comment on the pull request.

#### Scenario: Reads the checks of the head commit
- **WHEN** A test runs `devops pr evidence 42` against a recorded pull request with one head commit and two check runs.
- **THEN** The command requests the check runs for that head commit SHA and builds a table with both check runs.

#### Scenario: The comment holds the head commit and each check
- **WHEN** The recorded head commit has a passing check, a skipped check, and the pull request is a fix with a fail-to-pass check run.
- **THEN** The comment names the head commit, lists each check with its conclusion and link, links the fail-to-pass run, and names the skipped check on its own line.

#### Scenario: No fail-to-pass section for a pull request that is no fix
- **WHEN** A test runs the command for a pull request with a feat title and no fail-to-pass check run.
- **THEN** The comment text holds no fail-to-pass section and no fail-to-pass link.

### Requirement: devops pr evidence keeps one comment per pull request
The command SHALL keep one comment on a pull request by the marker line `<!-- devops-cli:pr-evidence -->`, SHALL update that comment on a new head commit, and MUST never post a second comment.

#### Scenario: Updates the marked comment
- **WHEN** A test runs the command twice and the recorded issue comments hold one comment with the marker line.
- **THEN** The second run sends one PATCH request for the marked comment and no POST request for a new comment.

#### Scenario: Posts one comment when none carries the marker
- **WHEN** A test runs the command against a recorded pull request whose issue comments hold no marker line.
- **THEN** The command sends one POST request and no PATCH request.

### Requirement: devops pr evidence takes no free text
The command MUST take no free text, and MUST take every number in the comment from the check runs that GitHub returns.

#### Scenario: Rejects a free-text option
- **WHEN** A test runs `devops pr evidence 42 --body '3 passed'`.
- **THEN** The command exits with a usage error and sends no request.

### Requirement: The dry run of devops pr evidence sends no request
The command SHALL print the comment text and the planned requests with `--dry-run`, and MUST send no write request.

#### Scenario: Dry run prints the plan
- **WHEN** A test runs `devops pr evidence 42 --dry-run` against a recorded pull request.
- **THEN** The command prints the comment text and the request plan and sends no write request.

### Requirement: An agent's comment ends with the attribution footer
The command SHALL end the comment with the attribution footer when an agent runs it.

#### Scenario: Agent attribution footer
- **WHEN** A test runs the command with the agent attribution setting and a recorded pull request.
- **THEN** The comment text ends with the attribution footer.
