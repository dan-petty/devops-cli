## ADDED Requirements

### Requirement: An unmatched criteria entry is refused
`criterion_problems` SHALL refuse each `criteria` entry whose text is not an acceptance criterion that a person wrote in the issue body, and SHALL match an entry to a criterion by its text with the whitespace collapsed. The problem MUST hold the text of the entry, and `check_gates` SHALL report it under `ProposalGate.CRITERIA`.

#### Scenario: Pasted requirement heading
- **WHEN** The refine block gives a `criteria` entry that is a pasted `### Requirement: ...` block, and no acceptance criterion of the issue has that text
- **THEN** `criterion_problems` returns one problem, and `check_gates` reports it under `ProposalGate.CRITERIA`

#### Scenario: Criterion copied from the issue
- **WHEN** A `criteria` entry copies one acceptance criterion of the issue character for character
- **THEN** `criterion_problems` returns no problem for that entry

#### Scenario: Problem names the entry
- **WHEN** `criterion_problems` refuses an unmatched `criteria` entry
- **THEN** the problem text holds the text of that entry

#### Scenario: An issue with no person-written list takes an empty list
- **WHEN** The issue body has no `Acceptance criteria` heading outside the refine block and the reply's `criteria` list is empty
- **THEN** `criterion_problems` returns no problem for the criteria mapping

### Requirement: The paths gate reads the body of a plan with a criteria list
The replay's `paths` gate SHALL give `check_proposal` the issue body of a plan that has a `criteria` list, and SHALL give no body for a plan that has none, so the criteria rule reads the same body as the stage job.

#### Scenario: A plan copies its issue's criteria
- **WHEN** The replay runs a plan whose `criteria` entries copy the criteria of its issue
- **THEN** the `paths` gate returns no problem for those entries

#### Scenario: A recorded plan has no list
- **WHEN** The replay runs a recorded plan with no `criteria` key
- **THEN** the `paths` gate judges no entry
