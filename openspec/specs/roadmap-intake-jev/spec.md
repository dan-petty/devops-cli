# roadmap-intake-jev Specification

## Purpose
Intake can ask TypeSafe Jev, a decision model with calibrated answers, for the fixed-list fields of a proposal in place of the `triage` model. This capability keeps Jev behind a setting that is off, makes a Jev failure fall back to the `triage` model, keeps a duplicate verdict a flag, and compares Jev with the `triage` model before anyone sets the setting.

## Requirements

### Requirement: Jev decides the proposal fields
With `roadmap.intake.jev` set, intake SHALL ask Jev, in one request, for the type of a candidate whose title and issue give none, for its priority, Value and Effort, and for a yes/no answer for each nearest item. The answers SHALL make the same `ModelProposal` that the `triage` model returns, so the checks of intake decide which values stand. With the setting off, intake SHALL not call Jev.

#### Scenario: Jev gives the fields
- **WHEN** the setting is on and Jev answers with a confidence of 0.90 or more
- **THEN** the proposal holds the type, priority, Value and Effort of the answers and the `triage` model is not called

#### Scenario: The title gives the type
- **WHEN** the title of the candidate has a Conventional Commit type
- **THEN** the request holds no type question

#### Scenario: The setting is off
- **WHEN** the setting is off
- **THEN** `build_intake_model()` returns the model of the `triage` task

### Requirement: A Jev failure falls back to the triage model
When a Jev request fails, times out, or gives a choice or score with a confidence below 0.60, intake SHALL use the `triage` model for the whole proposal, SHALL log a warning, and SHALL count each asked field with the outcome `fallback`. A proposal that Jev decides SHALL count each asked field with the outcome `jev`. The counter SHALL have the labels `field` and `outcome` only, and so at most 10 series.

#### Scenario: Jev is unavailable
- **WHEN** the gateway answers a Jev request with status 503
- **THEN** the `triage` model decides the proposal and the fields count `fallback`

#### Scenario: Jev is not sure
- **WHEN** a choice or score answer has a confidence of 0.40
- **THEN** the `triage` model decides the proposal

### Requirement: A Jev duplicate verdict only flags
A nearest item SHALL be the possible original only when its yes/no probability reaches 0.90. Intake SHALL place the candidate as it does for the `triage` model, and SHALL never close an issue or drop a candidate for a Jev verdict.

#### Scenario: An item reaches the bar
- **WHEN** Jev answers 0.90 for a nearest item
- **THEN** the decision names the item as the possible original, the outcome is to place the candidate, and no issue is closed

#### Scenario: An item stays below the bar
- **WHEN** Jev answers 0.85 for every nearest item
- **THEN** the decision names no possible original

### Requirement: The comparison with the triage model
`devops roadmap eval jev` SHALL run the duplicate cases of the intake evaluation set and the label cases through the `triage` model and through Jev without a fallback, SHALL print the false duplicates of each model first, then the agreement of each label field with the labels of the closed issues, and SHALL end with a verdict on the setting. It SHALL send no GitHub and no embedding request. It SHALL stop before its first call when it needs more calls than `--max-calls`.

#### Scenario: Jev flags every neighbour
- **WHEN** Jev answers 0.90 for the item of each case
- **THEN** the report counts one false duplicate for each case that a person judged new

#### Scenario: The run needs too many calls
- **WHEN** the run needs more calls than `--max-calls`
- **THEN** the command exits with code 2 and makes no call
