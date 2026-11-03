## ADDED Requirements

### Requirement: A long pull request body gets a warning
`devops pr check-readiness` SHALL print one warning when the body of the pull request, without its trailer lines, is longer than 1,000 characters. The warning SHALL name the length, the limit and `CONTRIBUTING.md` section 4. A trailer line is a line that starts with `Closes`, `Change:`, `Fail-to-pass:`, `Co-authored-by:` or `Signed-off-by:`, and it SHALL NOT count toward the length. A body that GitHub reports as `null` SHALL count as empty.

#### Scenario: The body is at the limit
- **WHEN** the body before the trailer lines is exactly 1,000 characters
- **THEN** the verdict holds no advisory

#### Scenario: The body is over the limit
- **WHEN** the body before the trailer lines is 1,001 characters
- **THEN** the verdict holds one WARNING advisory that names 1,001, 1,000 and `CONTRIBUTING.md` section 4

#### Scenario: Trailer lines do not count
- **WHEN** the body is 1,000 characters of text followed by a `Closes` line, a `Change:` line, a `Fail-to-pass:` line, a `Co-authored-by:` line and a `Signed-off-by:` line
- **THEN** the verdict holds no advisory

#### Scenario: The body is empty
- **WHEN** the REST payload of the pull request has `body` set to `null`
- **THEN** the verdict holds no advisory

### Requirement: The body warning blocks nothing
The warning for a long body SHALL NOT change the exit code of `devops pr check-readiness`.

#### Scenario: A long body and no blocker
- **WHEN** the body is 1,001 characters and nothing else blocks the pull request
- **THEN** `devops pr check-readiness` prints the warning and exits 0
