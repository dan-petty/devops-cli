## ADDED Requirements

### Requirement: One readiness function decides for every kind of draft pull request
The system SHALL provide one function that takes a pull request, its kind and its recorded item and returns ready, wait, or refuse with a reason, and the stage row and the implement job SHALL call it before marking a pull request ready.

#### Scenario: An incomplete implement pull request is refused
- **WHEN** the function reads a pull request of kind implement with one unticked task group
- **THEN** it returns refuse and the reason names the unticked group

#### Scenario: A complete plan pull request is ready
- **WHEN** the function reads an open stage plan pull request whose checks pass
- **THEN** it returns ready

#### Scenario: An author's pull request waits until the author says so
- **WHEN** the function reads a draft pull request of kind person whose author has not declared it complete
- **THEN** it returns wait

### Requirement: check-readiness names the unticked group
devops pr check-readiness SHALL report the refusal of the readiness function as one blocker and SHALL exit non-zero naming the unticked group of a refused implement pull request.

#### Scenario: A partial implement pull request blocks
- **WHEN** a user runs devops pr check-readiness on an implement pull request with an unticked group
- **THEN** the command exits non-zero and prints the name of the unticked group
