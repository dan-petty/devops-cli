## ADDED Requirements

### Requirement: A command reports a review session file that does not validate in one error line
When a review command reads a review session file that fails validation, the command SHALL print one error line that names the file path and the dotted field path of each failure, and SHALL exit with code 1. It SHALL print no traceback. This holds for `devops review findings`, `devops review verify`, `devops review intake` and `devops review corpus score`.

#### Scenario: A findings.json lacks a required field
- **WHEN** a `findings.json` has no `network_references.0.reputation.outcome` and a person runs `devops review findings`
- **THEN** the command exits with code 1, prints one error line that holds the file path and `network_references.0.reputation.outcome`, and prints no traceback

#### Scenario: Each reader reports the same file the same way
- **WHEN** a person runs `devops review verify`, `devops review intake` or `devops review corpus score` on that session
- **THEN** each command exits with code 1, prints one error line that holds the file path and `network_references.0.reputation.outcome`, and prints no traceback
