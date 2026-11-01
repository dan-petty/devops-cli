## ADDED Requirements

### Requirement: The log lines of the snapshot are decoded and masked text
The doctor SHALL read the log of a flagged pod as UTF-8 text, with each line of the log as one line of the snapshot, and SHALL mask secrets in each line.

#### Scenario: A log of several lines
- **WHEN** the log of a flagged pod is the bytes of three lines, one with a check mark and one with a token
- **THEN** the snapshot holds three lines for the pod, the check mark is the character, and the token is masked
