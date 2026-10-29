## ADDED Requirements

### Requirement: Refine writes each acceptance criterion as an OpenSpec requirement
The refine reply SHALL give each acceptance criterion as `name`, `requirement`, `scenario`, `when` and `then`, and the proposed design SHALL render it as an OpenSpec requirement block: `### Requirement: <name>`, the requirement text, `#### Scenario: <scenario>`, and the `- **WHEN**` and `- **THEN**` lines.

#### Scenario: A criterion in the proposed design
- **WHEN** refine renders a proposal whose criterion has the name `Token cost`, the requirement `The tuner SHALL read the token cost from the ledger.`, the scenario `The ledger has the backend`, the WHEN `the ledger holds records for the backend` and the THEN `the tuner sends no probe`
- **THEN** the section holds `### Requirement: Token cost`, the requirement line, `#### Scenario: The ledger has the backend`, `- **WHEN** the ledger holds records for the backend` and `- **THEN** the tuner sends no probe`, and no `Criterion` or `Verification:` line

#### Scenario: A criterion with the old keys
- **WHEN** a reply gives a criterion as `description` and `verification`
- **THEN** the reply fails validation

### Requirement: A criterion's requirement says SHALL or MUST
The refine reply SHALL be refused when the `requirement` of a criterion does not contain the word SHALL or MUST, as OpenSpec requires of a requirement's text.

#### Scenario: A requirement without the keyword
- **WHEN** a reply's criterion has the requirement `The tuner reads the ledger.`
- **THEN** the reply fails validation with an error that names SHALL and MUST

### Requirement: Refine answers the existing-tool question
The refine reply SHALL carry `existing_tool`: the open, maintained tool or library that covers the need and what it lacks, or the written cost of building instead. Refine SHALL set an item Ready only when that answer is not empty, and SHALL render it under `### Existing Tool Considered`.

#### Scenario: The answer in the proposed design
- **WHEN** refine renders a proposal whose `existing_tool` is `Renovate covers the pin.`
- **THEN** the section holds a `### Existing Tool Considered` heading followed by that text

#### Scenario: An empty answer
- **WHEN** a proposal meets every other readiness rule and its `existing_tool` is empty
- **THEN** refine does not set the item Ready

#### Scenario: A reply without the key
- **WHEN** a reply has no `existing_tool` key
- **THEN** the reply fails validation
