## ADDED Requirements

### Requirement: The stage reply holds structured constant claims
`StageProposal` SHALL hold `constant_claims`, a list of `StageConstantClaim` entries that each give a constant `name` and an integer `value`, and the list MUST be empty when a reply omits it. `StageConstantClaim` MUST refuse a `name` that is not a Python identifier.

#### Scenario: A reply with one claim
- **WHEN** A reply gives `constant_claims` with the name `SUMMARY_MAX_CHARS` and the value 60.
- **THEN** The validated proposal holds one entry, and the entry keeps the name `SUMMARY_MAX_CHARS` and the value 60.

#### Scenario: A reply with no claim list
- **WHEN** A reply gives no `constant_claims`.
- **THEN** The validated proposal holds an empty `constant_claims` and no validation error.

#### Scenario: A name with a hyphen
- **WHEN** A reply gives the claim name `SUMMARY-MAX`.
- **THEN** Validation raises an error for `constant_claims`.

### Requirement: A structured claim matches the staged value
`check_proposal` SHALL refuse a claim whose value differs from the staged value of its name, and the message SHALL name the constant and the staged value. `check_proposal` SHALL refuse a claim whose name the staged values do not hold, and the message SHALL name the constant.

#### Scenario: A claim with the staged value
- **WHEN** The plan claims `SUMMARY_MAX_CHARS` with the value 60, and the staged value is 60.
- **THEN** No problem names `SUMMARY_MAX_CHARS`.

#### Scenario: A claim with another value
- **WHEN** The plan claims `SUMMARY_MAX_CHARS` with the value 40, and the staged value is 60.
- **THEN** One problem names `SUMMARY_MAX_CHARS` and the staged value 60.

#### Scenario: A claim the staged values do not hold
- **WHEN** The plan claims `PLAN_SUMMARY_MAX_CHARS` with the value 47, and the staged values hold no such name.
- **THEN** One problem names `PLAN_SUMMARY_MAX_CHARS`.

### Requirement: The prose scan runs only when the claim list is empty
`check_proposal` SHALL run the prose scan of constant claims only when `constant_claims` is empty.

#### Scenario: A reply with no claim list and a prose claim
- **WHEN** A reply gives no `constant_claims`, and a design decision quotes `SUMMARY_MAX_CHARS: Final[int] = 40` while the staged tree sets `SUMMARY_MAX_CHARS = 60`.
- **THEN** The check returns the prose problem for that sentence.

#### Scenario: A reply with a claim list and a prose claim
- **WHEN** A reply gives a claim for `SUMMARY_MAX_CHARS` and a sentence holds two numbers beside it.
- **THEN** The check returns no prose problem for that sentence.

### Requirement: A caller with no staged values judges no claim
`check_proposal` SHALL judge no constant claim when its caller gives no staged values.

#### Scenario: A caller with no staged values
- **WHEN** `check_proposal` runs with no `constants` argument on a plan whose claim list holds a claim for `SUMMARY_MAX_CHARS`.
- **THEN** No problem names `SUMMARY_MAX_CHARS`.

### Requirement: The stage job reads the value of each claimed name
The stage job SHALL read the staged value of each name in `constant_claims` and pass it to `check_proposal`.

#### Scenario: A claim of a name no plan text cites
- **WHEN** A reply claims `SUMMARY_MAX_CHARS` and no plan text names the constant.
- **THEN** The job reads the staged value 60 for the claim.

## MODIFIED Requirements

### Requirement: The prose scan ignores a constant that the staged tree does not define
The prose scan of constant claims MUST skip a constant name that the staged tree does not define as a module-level integer assignment.

#### Scenario: New plan constant
- **WHEN** A design decision names `PLAN_SUMMARY_MAX_CHARS = 47`, and the staged tree does not define `PLAN_SUMMARY_MAX_CHARS`.
- **THEN** The check returns no problem about `PLAN_SUMMARY_MAX_CHARS`.

#### Scenario: Non-literal assignment
- **WHEN** A staged module sets `SUMMARY_MAX_CHARS` from a call, and the plan gives it the value 40.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`.

#### Scenario: Ambiguous definition
- **WHEN** Two staged modules set `SUMMARY_MAX_CHARS` to different integers, and the plan gives it the value 40.
- **THEN** The check returns no problem about `SUMMARY_MAX_CHARS`, because the tree holds no one value.

### Requirement: The prompt asks for the staged value of a constant
The plan stage prompt SHALL list `constant_claims` among the reply keys and tell the model to cite the staged value of each constant that the plan relies on, with the constant name and its value, and to give no new name to the bound of a constant that the staged tree defines. It SHALL state that a claim names a constant that the staged tree defines, and that a constant the plan creates is no claim.

#### Scenario: Prompt rule
- **WHEN** The prompt rules test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** The text holds an instruction to cite the staged value of each constant that the plan relies on.

#### Scenario: Prompt claim rule
- **WHEN** The test reads the text of `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** The text holds the sentence that a claim names a constant of the staged tree and that a constant the plan creates is no claim.

## RENAMED Requirements

- FROM: `### Requirement: A constant that the staged tree does not define is ignored`
- TO: `### Requirement: The prose scan ignores a constant that the staged tree does not define`
