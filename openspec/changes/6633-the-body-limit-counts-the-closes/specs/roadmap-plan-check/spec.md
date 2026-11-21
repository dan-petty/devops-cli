## MODIFIED Requirements

### Requirement: Plan-check checks the body of the pull request
The command SHALL report a problem when the text above the `Plans` line, with its trailing blank lines removed, is longer than `BODY_MAX_CHARS`, when the body holds no `Plans #<issue>` reference, or when the body holds a closing keyword before an issue reference. The `Plans` line, the `Change:` line and the lines after it SHALL NOT count toward the limit.

#### Scenario: A missing plan reference is reported
- **WHEN** the pull request body holds no `Plans #` line
- **THEN** the output names the body rule and the exit code is 1.

#### Scenario: A closing keyword is reported
- **WHEN** the pull request body holds `Closes #3201`
- **THEN** the output names the closing keyword and the exit code is 1.

#### Scenario: A long body is reported
- **WHEN** the text above `Plans` has 1,001 characters and the `Plans` and `Change:` lines add 120 characters
- **THEN** the output names the body length rule and the exit code is 1.

#### Scenario: A body at the limit above Plans is accepted
- **WHEN** the text above `Plans` has 1,000 characters and the `Plans` and `Change:` lines add 120 characters
- **THEN** the output reports no body length problem
