## ADDED Requirements

### Requirement: The plan reader reads the weakened checks of a plan
`read_change` SHALL read each bullet of the `## Weakened checks` section of `proposal.md` into `StageProposal.weakened_checks`, with the fields `check`, `stopped` and `safeguard`. The form of a bullet is `- **<check>**: Stopped: <stopped> Safeguard: <safeguard>`. The reader MUST raise `PlanReadError` that names `proposal.md` for a line of the section in another form. The field MUST NOT be in the JSON schema of the reply.

#### Scenario: A section with two entries
- **WHEN** `proposal.md` holds two entries in the form
- **THEN** `read_change` gives both, each with its check, what it stopped and its safeguard

#### Scenario: A plan with no section
- **WHEN** `proposal.md` holds no `## Weakened checks` section
- **THEN** `read_change` gives an empty list

#### Scenario: An entry with no safeguard
- **WHEN** a bullet of the section holds no `Safeguard:` text
- **THEN** `read_change` raises `PlanReadError` for `proposal.md` that holds the bullet

#### Scenario: The reply schema
- **WHEN** a test reads `StageProposal.model_json_schema()`
- **THEN** its properties do not hold `weakened_checks`
