## ADDED Requirements

### Requirement: scope-splitting-on-unworkable-parts
When refine identifies parts of an issue that cannot be implemented as written or have unresolved questions, it SHALL remove those parts from the core proposal and list them in a split_issues array, each entry holding a title and a body.

#### Scenario: unworkable part removed from proposal
- **WHEN** refine identifies a part of the issue that cannot be implemented as written
- **THEN** the proposal excludes that part and the split_issues array contains an entry with a title and body for that part

#### Scenario: workable scope proceeds toward Ready
- **WHEN** refine splits unworkable scope from an issue that also has workable scope
- **THEN** the remaining proposal covers only the workable scope and is eligible for Ready status

### Requirement: split-issue-creation-via-intake
The orchestrator SHALL create a new issue on the roadmap for each entry in the split_issues array, using the existing intake path.

#### Scenario: one issue per split entry
- **WHEN** the refine response contains a split_issues array with two entries
- **THEN** the orchestrator calls intake twice and two new issues appear on the roadmap with the titles and bodies from the entries

### Requirement: split-issue-linking
The orchestrator SHALL record a link between the original issue and each newly created issue by adding a comment on the original issue that names each new issue number.

#### Scenario: link recorded on original issue
- **WHEN** the orchestrator creates a new issue from a split_issues entry
- **THEN** a comment on the original issue names the new issue number as a cross-reference
