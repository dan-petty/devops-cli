## ADDED Requirements

### Requirement: A cited command that omits a required option is refused
The plan check SHALL refuse a plan that cites a `devops` command line that gives a token after the command path and omits a required option of that command, and the problem SHALL name the option.

#### Scenario: The summary option is missing from a plan line
- **WHEN** a plan cites `devops pr describe 1` in its Feasibility text
- **THEN** the citation gate returns a problem that names `--summary`, and the plan check refuses the plan
