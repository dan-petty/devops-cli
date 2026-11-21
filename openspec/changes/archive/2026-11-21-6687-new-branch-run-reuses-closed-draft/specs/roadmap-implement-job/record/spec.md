## MODIFIED Requirements

### Requirement: Prepare clears the marks of the run before
`prepare` SHALL clear the marks of the run before: `implement.trace`, `implement.result`, `implement.published_sha` and `implement.repair_rounds`. It SHALL write `implement.pr` with the pull request of the target, or clear it for a new branch.

#### Scenario: The repair rounds of the Job before
- **WHEN** the record holds 3 repair rounds of the Job before, and a new Job starts
- **THEN** `prepare` clears `implement.repair_rounds`

#### Scenario: A draft that a person closed
- **WHEN** the first Job opened draft 5 and stopped, a person deleted the branch, and the next Job runs
- **THEN** the next Job opens a new draft for its branch and writes nothing to draft 5
