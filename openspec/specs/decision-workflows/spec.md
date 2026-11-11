# decision-workflows Specification

## Purpose
A decision point is a named place in a Service workflow where the workflow picks one outcome of a closed set. This capability fixes the unit: the registry of points, the resolver chain (a rule, then a decision model, then the current behavior), the settings that switch a point, the records that join a decision with its outcome, and the one metric. The rules come from ADR 0020. They build on the rules of a decision step in `decision-steps` (ADR 0019).

## Requirements

### Requirement: A decision point is a registered unit
Each decision point SHALL have one entry in a registry. The entry SHALL hold the name of the point, its closed question set, its evidence builder, its action bands and the path of its cuts file. The name SHALL be of the form `<area>.<what>`. A point SHALL return a band and SHALL NOT return a text.

#### Scenario: The registry holds the point
- **WHEN** a test reads the registry
- **THEN** each entry has a name of the form `<area>.<what>`, a question set that does not change with the input, and a cuts file in the repository

### Requirement: The resolver chain goes rule, decision model, current behavior
The registry SHALL resolve a point with the first resolver that answers, in this order: the deterministic rule of the point, if it has one; the decision model, if `ai.decision_model` is set and the mode of the point is `shadow` or `on`; the current behavior of the workflow. A point SHALL have a rule only when the rule meets the bar of the point on the half of the labelled cases that was not fitted. A point whose rule meets its bar SHALL have no model resolver.

#### Scenario: A rule answers first
- **WHEN** a point has a rule and a decision model, and the rule answers
- **THEN** the band is the band of the rule, the resolver is `rule`, and no request goes to the decision model

#### Scenario: The model answers when no rule does
- **WHEN** a point has no rule, `ai.decision_model` is set, the mode is `on`, and the model answers with a confidence at or above the floor
- **THEN** the band follows the cuts and the resolver is `model`

#### Scenario: Nothing answers
- **WHEN** no resolver answers
- **THEN** the workflow runs its current behavior and the resolver is `fallback`

### Requirement: No decision model configured means today's behavior
With `ai.decision_model` empty, a point that has no rule SHALL send no request to any model, SHALL write no metric series and SHALL leave the workflow as it is without the point. A point that has a rule SHALL still run the rule when its mode is `shadow` or `on`. The setting `ai.decision_model` SHALL accept only the name of a System One decision model.

#### Scenario: Empty model name
- **WHEN** `ai.decision_model` is empty and a workflow reaches a point with the mode `on`
- **THEN** the fake decision model gets no request, no counter changes, and the result of the workflow is the same as with the mode `off`

#### Scenario: A name that is not a decision model
- **WHEN** the settings load with `ai.decision_model` set to the name of a model that writes text
- **THEN** the load fails and the error names the setting

### Requirement: The mode of each point is a setting
The setting `roadmap.decisions` SHALL map the name of a point to a mode: `off`, `shadow` or `on`. A point that is not in the mapping SHALL be `off`. A key that is not the name of a registered point SHALL make the settings fail to load. The registry SHALL refuse the mode `on` for a point that has no fitted cuts in the repository.

#### Scenario: A key that names no point
- **WHEN** the settings load with a key of `roadmap.decisions` that is not a registered point
- **THEN** the load fails and the error names the key and the registered points

#### Scenario: On without cuts
- **WHEN** the settings load with the mode `on` for a point that has no fitted cuts
- **THEN** the load fails and the error names the point

### Requirement: Shadow records and changes nothing
In the mode `shadow`, the chain SHALL run, the registry SHALL record its answer, and the workflow SHALL act as with the mode `off`. A decision SHALL have an identifier of the point, the subject and a sequence number. Its record SHALL hold the identifier, the mode, the resolver, the band, the model, the date of the cuts and the answers. A digest of text SHALL be in the record only as a hash. A digest of counts MAY be in the record.

#### Scenario: Shadow leaves the result alone
- **WHEN** a workflow runs a point in `shadow` with the fake decision model
- **THEN** the workflow result equals the result with the mode `off`, one record and one counter increment name the band, and the record holds no text of the digest

### Requirement: A point fails back
A point SHALL fall back to the current behavior when the decision model raises an error, times out, leaves a question unanswered, answers with a confidence under the floor of the cuts, or when the digest holds a secret. The registry SHALL log the cause and SHALL count the case with the resolver `fallback` and the band `none`.

#### Scenario: The model fails
- **WHEN** the fake decision model raises an error
- **THEN** the current behavior runs, one log record names the error, and the counter has one increment with the resolver `fallback`

### Requirement: Cuts and rule parameters are data with their provenance
The cuts of a point, and the parameters of its rule, SHALL be read from a data file in the repository. The file SHALL record the model, the date, the cases, the split of the cases and the numbers that gave the values. A cut in a constant SHALL NOT be used.

#### Scenario: The cuts file names its fit
- **WHEN** a test loads the cuts file of each registered point
- **THEN** each file names the model, the date, the number of cases and the report of the fit

### Requirement: A decision joins with its outcome
The workflow SHALL write one outcome record with the identifier of the decision when the real result is known. A helper SHALL join decision records and outcome records by identifier and SHALL return labelled cases for the fit. A decision with no outcome SHALL stay out of the labelled cases.

#### Scenario: The join
- **WHEN** a test gives the helper three decision records and two outcome records with matching identifiers
- **THEN** it returns two labelled cases and reports one decision with no outcome

### Requirement: One bounded metric counts the decisions
The counter `devops_cli_decision_point_total` SHALL count the decisions with the labels `point`, `resolver` (`rule`, `model` or `fallback`), `band` (`continue`, `review`, `flag` or `none`) and `mode` (`shadow` or `on`). A point with the mode `off` SHALL write no series. The documents SHALL state the series count of the catalogue.

#### Scenario: The labels are bounded
- **WHEN** a test runs every registered point in every mode with every resolver
- **THEN** the counter has at most 14 series for each point, 8 for a point with one resolver besides the fallback, and no label value is outside the sets above

### Requirement: A point has its bar before it is built
The record of a decision point SHALL give, before the point is built, its question set, its evidence fields, its baseline rule, its label source and its success bar. The bar SHALL be checked against the oracle of the labelled data, and a bar above the oracle SHALL NOT be set.

#### Scenario: The catalogue is complete
- **WHEN** a reviewer reads the catalogue of ADR 0020
- **THEN** each point that is built or planned has the five items above

### Requirement: The two settings of the decision points have variables
The variable `DEVOPS_CLI_AI_DECISION_MODEL` SHALL set `ai.decision_model`. The variable `DEVOPS_CLI_ROADMAP_DECISIONS` SHALL set `roadmap.decisions` from a JSON object of point names and modes, and `devops config set roadmap.decisions` SHALL take the same JSON object. A value that is no JSON object SHALL make the settings fail to load, and the error SHALL name the setting.

#### Scenario: The variable sets the mode of a point
- **WHEN** the settings load with `DEVOPS_CLI_ROADMAP_DECISIONS` set to `{"stage.verify_screen": "shadow"}` and `DEVOPS_CLI_AI_DECISION_MODEL` set to `typesafe/jev-1.14`
- **THEN** `roadmap.decisions` maps `stage.verify_screen` to `shadow` and `ai.decision_model` is `typesafe/jev-1.14`

#### Scenario: A value that is no JSON object
- **WHEN** the settings load with `DEVOPS_CLI_ROADMAP_DECISIONS` set to `shadow`
- **THEN** the load fails and the error names `roadmap.decisions`

### Requirement: The registry bounds the series of its catalogue
The registry SHALL refuse a catalogue of points whose label sets of `devops_cli_decision_point_total` are more than 60. A point SHALL list the label sets that it can write: the bands `continue`, `review` and `flag` for each resolver that it has besides the fallback, and `none` for the fallback, in the modes `shadow` and `on`.

#### Scenario: Too many points
- **WHEN** a test builds a registry of eight points that can each write 8 label sets
- **THEN** the registry raises an error that names the bound of 60

### Requirement: The settings check the modes without the points
The settings SHALL check the keys and the modes of `roadmap.decisions` against a table of the name and the cuts file of each point, and SHALL NOT import `pydantic_ai` or a point module to do it. The table SHALL hold the same names and cuts files as the registry.

#### Scenario: The table and the registry agree
- **WHEN** a test reads the table and the registry
- **THEN** the names and the cuts files of the two are equal

#### Scenario: On without a cuts file
- **WHEN** a test checks the mode `on` for a point of a table whose cuts file does not exist
- **THEN** the check fails and the error names the point and the file
