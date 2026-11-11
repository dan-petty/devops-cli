## ADDED Requirements

### Requirement: A new issue makes intake due at the next poll
The poll SHALL run intake when the repository has an issue newer than the newest issue that the intake record keeps, also before intake's interval. An intake round SHALL keep the newest issue as the round starts. A scoped update SHALL keep it as it was. A newer pull request SHALL not make intake due.

#### Scenario: The delivery of a new issue is lost
- **WHEN** intake decided candidate 1, candidate 2 opens, no scoped update runs for it, and a poll comes five minutes later
- **THEN** the poll runs intake and the model judges candidate 2

#### Scenario: A new pull request
- **WHEN** a pull request opens after the last intake round, and no issue opens
- **THEN** the next poll runs no intake

#### Scenario: The scoped update decided the new issue
- **WHEN** the scoped update of new candidate 2 decided it, and a poll comes four minutes later
- **THEN** the poll runs intake, the model judges nothing in that round, and the poll after it runs no intake
