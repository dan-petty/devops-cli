## MODIFIED Requirements

### Requirement: Jev decides the proposal fields
With `roadmap.intake.jev` set to `on`, intake SHALL ask Jev, in one request, for the type of a candidate whose title and issue give none, for its priority, Value and Effort, and for a yes/no answer for each nearest item. The answers SHALL make the same `ModelProposal` that the `triage` model returns, so the checks of intake decide which values stand. With the setting `off`, intake SHALL not call Jev. The setting SHALL be `off`, `shadow` or `on`, and `off` SHALL be the default.

#### Scenario: Jev gives the fields
- **WHEN** the setting is `on` and Jev answers with a confidence of 0.90 or more
- **THEN** the proposal holds the type, priority, Value and Effort of the answers and the `triage` model is not called

#### Scenario: The title gives the type
- **WHEN** the title of the candidate has a Conventional Commit type
- **THEN** the request holds no type question

#### Scenario: The setting is off
- **WHEN** the setting is `off`
- **THEN** `build_intake_model()` returns the model of the `triage` task and no Jev request is made

#### Scenario: The old bool is refused
- **WHEN** the setting is the bool `true`
- **THEN** the settings fail to validate

### Requirement: A Jev failure falls back to the triage model
When the setting is `on` and a Jev request fails, times out, or gives a choice or score with a confidence below 0.60, intake SHALL use the `triage` model for the whole proposal, SHALL log a warning, and SHALL count each asked field with the outcome `fallback`. A proposal that Jev decides SHALL count each asked field with the outcome `jev`. The counter SHALL have the labels `field` and `outcome` only, and so at most 10 series. Mode `shadow` SHALL not count in this counter.

#### Scenario: Jev is unavailable
- **WHEN** the gateway answers a Jev request with status 503
- **THEN** the `triage` model decides the proposal and the fields count `fallback`

#### Scenario: Jev is not sure
- **WHEN** a choice or score answer has a confidence of 0.40
- **THEN** the `triage` model decides the proposal

## ADDED Requirements

### Requirement: Shadow mode answers beside the triage model
With the setting `shadow`, intake SHALL use the `triage` model for every label and every flag, as it does with `off`. After the checks accept the `triage` reply, intake SHALL ask Jev the same questions in one request for each candidate, and SHALL change no label, no flag, no comment and no placement because of the answers. A Jev error or timeout SHALL change nothing. A possible duplicate that Jev flags SHALL only be recorded, and intake SHALL never close an issue or drop a candidate for it.

#### Scenario: Jev differs on every field
- **WHEN** the setting is `shadow` and Jev answers another type, priority, Value, Effort and a flag
- **THEN** the decision shows the type, priority, Value, Effort and possible duplicate of the `triage` model

#### Scenario: Jev fails in shadow
- **WHEN** the setting is `shadow` and the gateway answers a Jev request with status 503
- **THEN** the candidate is placed as with `off`, the issue gets no shadow mark, and each asked field counts `jev_error`

#### Scenario: A triage reply is unusable
- **WHEN** the setting is `shadow` and the `triage` model gives no usable reply
- **THEN** intake sends no Jev request for the candidate

### Requirement: Shadow mode records the observation in the job record
In mode `shadow`, the placement of a candidate SHALL write the mark `intake.jev_shadow` in the job record of the issue, in the same write as the Priority. The mark SHALL hold the time of the proposal and, for each asked field, the Jev answer, its probability and the `triage` answer. It SHALL hold no text of the issue.

#### Scenario: A placement records the answers
- **WHEN** the setting is `shadow` and intake places a candidate
- **THEN** the job record of the issue holds the mark with the answers and probabilities of type, priority, Value and Effort

#### Scenario: A neighbour stays below the bar
- **WHEN** Jev answers 0.40 for the one nearest item
- **THEN** the duplicate field holds an empty Jev answer and the probability 0.40

#### Scenario: The mark holds no issue text
- **WHEN** a candidate with a title and a body is placed in mode `shadow`
- **THEN** the mark holds none of the words of the title and the body

### Requirement: The duplicate field of the record shows the probability
In the mark, the Jev answer of the duplicate field SHALL be the nearest item whose probability reaches 0.90, or empty. Its probability SHALL be the highest probability of any nearest item. The `triage` answer SHALL be the checked possible original, or empty.

#### Scenario: A neighbour reaches the bar
- **WHEN** Jev answers 0.90 for the one nearest item and the `triage` model names the same item
- **THEN** the duplicate field holds that item number in both answers and the probability 0.90

### Requirement: Shadow mode counts the agreement of Jev
In mode `shadow`, intake SHALL count each asked field of each candidate in `devops_cli_roadmap_intake_jev_shadow_total` with the labels `field` (type, priority, value, effort, duplicate) and `outcome` only: `agree` when the Jev answer equals the `triage` answer, `differ` when it does not, and `jev_error` when Jev gave no answer. The counter SHALL have at most 15 series.

#### Scenario: Jev agrees on two fields
- **WHEN** Jev answers the priority and the Effort of the `triage` model and another type and Value
- **THEN** the counter holds `agree` for priority and effort and `differ` for type and value

### Requirement: The report of the shadow records
`devops roadmap eval jev --from-shadow` SHALL join the mark `intake.jev_shadow` of each issue with the labels of the issue now. For each of type, priority, value and effort it SHALL print the agreement of Jev and the `triage` model, how often each equals the final label, how often only one does, and how often Jev equals it in each band of its probability. It SHALL print the duplicate flags against the issues closed as a duplicate. It SHALL make no model request and no write.

#### Scenario: A person changes a label
- **WHEN** Jev answered P1-High, the `triage` model answered P2-Medium, and a person set P1-High
- **THEN** the report counts one record where only Jev equals the final label

#### Scenario: No issue holds a mark
- **WHEN** no issue holds the mark
- **THEN** the report says so and names the setting `shadow`

#### Scenario: A dry run
- **WHEN** the command runs with `--from-shadow --dry-run`
- **THEN** it opens no store and makes no request
