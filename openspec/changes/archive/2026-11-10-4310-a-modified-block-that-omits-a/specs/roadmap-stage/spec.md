## ADDED Requirements

### Requirement: A MODIFIED requirement gets the base scenarios that it omits
The stage job SHALL add each scenario of the base requirement that a MODIFIED block omits to that block, with the raw text that `openspec show <capability> --type spec --json` gives, before it validates the change. It SHALL write the files that it validated. It SHALL keep the scenarios of the reply in their own text and order, and append the omitted scenarios after them.

#### Scenario: One base scenario omitted
- **WHEN** a plan holds a MODIFIED requirement that omits one scenario of the base requirement
- **THEN** the files that the job writes hold all base scenarios in the block

#### Scenario: Reply adds and changes scenarios
- **WHEN** a MODIFIED block has a changed scenario and a new scenario, and omits a base scenario
- **THEN** the block keeps the changed text and the new scenario, and ends with the omitted base scenario

### Requirement: The repair leaves a complete block and other sections alone
The repair MUST NOT change a file when each MODIFIED block names every scenario of its base requirement. It SHALL NOT change an ADDED requirement, and SHALL NOT change a MODIFIED requirement that the base spec lacks, so OpenSpec still reports that problem.

#### Scenario: No scenario omitted
- **WHEN** a plan holds a MODIFIED block that names every base scenario
- **THEN** the spec file of the change equals the rendered reply

#### Scenario: MODIFIED of an unknown requirement
- **WHEN** a MODIFIED block names a requirement that the base spec does not hold
- **THEN** the block is unchanged and the validation problem still reaches the model
