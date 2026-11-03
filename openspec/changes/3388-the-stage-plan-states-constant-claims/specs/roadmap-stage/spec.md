## ADDED Requirements

### Requirement: The plan states a constant claim as a name and a value
`StageProposal` SHALL hold `constant_claims`, a list of entries that each give a constant `name` and an integer `value`.

#### Scenario: A reply with one claim
- **WHEN** a reply gives `constant_claims` with the name `BODY_MAX_CHARS` and the value 800
- **THEN** the validated proposal holds one entry, and the entry keeps the name `BODY_MAX_CHARS` and the value 800

### Requirement: A claim name is an identifier
`StageConstantClaim` MUST refuse a `name` that is not a Python identifier.

#### Scenario: A name with a hyphen
- **WHEN** a reply gives the claim name `BODY-MAX`
- **THEN** `StageProposal.model_validate` raises a validation error for `constant_claims`

### Requirement: The prompt lists the claim key
The stage prompt SHALL list `constant_claims` among the reply keys and state that the plan lists each constant it relies on with its staged value.

#### Scenario: The prompt key test
- **WHEN** the test reads the reply keys of `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the keys equal the fields of `StageProposal`, and `constant_claims` is one of them

### Requirement: The reader gives the staged value
`staged_constants` SHALL return the integer value of each claimed name that the staged commit defines as a module-level literal under `src/`.

#### Scenario: A literal constant at the commit
- **WHEN** the staged commit holds `BODY_MAX_CHARS: Final[int] = 800` in `src/devops_cli/roadmap/stage_change.py` and the plan claims `BODY_MAX_CHARS`
- **THEN** `staged_constants` returns 800 for `BODY_MAX_CHARS`

### Requirement: A correct claim passes
`check_proposal` SHALL return no constant-claim problem for a claim whose value equals the staged value.

#### Scenario: A claim with the staged value
- **WHEN** the plan claims `BODY_MAX_CHARS` is 800 and the staged value is 800
- **THEN** no problem names `BODY_MAX_CHARS`

### Requirement: A wrong claim is refused
`check_proposal` SHALL refuse a claim whose value differs from the staged value, and the message SHALL name the constant and the staged value.

#### Scenario: A claim with another value
- **WHEN** the plan claims `BODY_MAX_CHARS` is 900 and the staged value is 800
- **THEN** one problem names `BODY_MAX_CHARS` and `800`

### Requirement: A claim with no staged definition is refused
`check_proposal` SHALL refuse a claim whose name the staged tree defines as no module-level integer literal, and the message SHALL name the constant.

#### Scenario: An invented name
- **WHEN** the plan claims `PLAN_SUMMARY_MAX_CHARS` is 47 and no module of `src/` defines it
- **THEN** one problem names `PLAN_SUMMARY_MAX_CHARS`

### Requirement: The prose scan stays as the fallback
`check_proposal` SHALL run the existing prose scan of constant claims only when `constant_claims` is empty.

#### Scenario: A reply with no claim list
- **WHEN** a reply gives no `constant_claims` and states a constant claim in prose
- **THEN** `check_proposal` returns the prose problem for that text

### Requirement: The replay judges no claim
`check_proposal` SHALL judge no constant claim when the caller gives no staged values.

#### Scenario: A caller with no staged values
- **WHEN** `check_proposal` runs with no `constants` argument on a plan that claims `BODY_MAX_CHARS` is 900
- **THEN** no problem names `BODY_MAX_CHARS`
