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
A point SHALL fall back to the current behavior when the decision model raises an error, times out, leaves a question unanswered, answers with a confidence under the floor of the cuts, or when the digest holds a secret. It SHALL give the fallback for every error of the chain, including an error that no class names, and SHALL NOT raise that error to the caller. The registry SHALL log the cause and SHALL count the case with the resolver `fallback` and the band `none`.

#### Scenario: The model fails
- **WHEN** The fake decision model raises an error
- **THEN** The current behavior runs, one log record names the error, and the counter has one increment with the resolver `fallback`

#### Scenario: An error that no class names
- **WHEN** The fake decision model raises `RuntimeError` inside the chain
- **THEN** The decision is the fallback with the band `none`, no error reaches the caller, and the failed counter adds one count with `error` equal to `other`

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
The registry SHALL refuse a catalogue of points whose label sets of `devops_cli_decision_point_total` are more than 92, the bound of ADR 0020 section 7 that `CONST_ROADMAP_DECISION_POINT_MAX_SERIES` holds. A point SHALL list the label sets that it can write: the bands `continue`, `review` and `flag` for each resolver that it has besides the fallback, and `none` for the fallback, in the modes `shadow` and `on`.

#### Scenario: Too many points
- **WHEN** A test builds a catalogue whose label sets are more than `CONST_ROADMAP_DECISION_POINT_MAX_SERIES`
- **THEN** The registry raises an error that names the bound that the constant holds

#### Scenario: The catalogue at the bound
- **WHEN** A test builds a registry whose label sets are exactly `CONST_ROADMAP_DECISION_POINT_MAX_SERIES`
- **THEN** The registry loads and its series count equals the constant

### Requirement: The settings check the modes without the points
The settings SHALL check the keys and the modes of `roadmap.decisions` against a table of the name and the cuts file of each point, and SHALL NOT import `pydantic_ai` or a point module to do it. The table SHALL hold the same names and cuts files as the registry. The settings SHALL refuse the mode `shadow` and the mode `on` for a point whose cuts file is not in the repository, and the error SHALL name the point and the path.

#### Scenario: The table and the registry agree
- **WHEN** A test reads the table and the registry
- **THEN** The names and the cuts files of the two are equal

#### Scenario: On without a cuts file
- **WHEN** A test checks the mode `on` for a point of a table whose cuts file does not exist
- **THEN** The check fails and the error names the point and the file

#### Scenario: Shadow without a cuts file
- **WHEN** A test checks the mode `shadow` for a point of a table whose cuts file does not exist
- **THEN** The check fails and the error names the point and the file

### Requirement: An async caller awaits the decision
`ResolverChain` SHALL give `adecide`, an async method that awaits the gathered request of the point on the event loop of its caller and uses no blocking portal. `adecide` SHALL write the decision record and the counts of the decision as `decide` does.

#### Scenario: A caller awaits adecide
- **WHEN** A coroutine awaits `chain.adecide(given, subject=1)` with a fake decision model
- **THEN** It returns the decision of the model, writes one decision record and raises no error

### Requirement: Each decision adds its duration
Each decision SHALL add one observation to the histogram `devops_cli_decision_point_duration_seconds`, with the labels `point` and `resolver`. A point SHALL add at most 3 series to the histogram, one for each resolver of the chain.

#### Scenario: One decision, one sample
- **WHEN** A point decides one case with the model and its cuts
- **THEN** The histogram holds one sample for that point with the resolver `model`

#### Scenario: A fallback is timed too
- **WHEN** The chain gives the fallback for a case
- **THEN** The histogram holds one sample for that point with the resolver `fallback`

### Requirement: Each failed request counts by class
Each failed request of a point SHALL add one to the counter `devops_cli_decision_point_failed_total`, with the labels `point` and `error`. The value of `error` SHALL be one of `timeout`, `model_error`, `parse`, `secret`, `no_cuts`, `model_mismatch` or `other`, so a point SHALL add at most 7 series to the counter.

#### Scenario: A timeout
- **WHEN** The decision model does not answer within the timeout of the point
- **THEN** The counter adds one count for that point with `error` equal to `timeout`

#### Scenario: A secret in the digest
- **WHEN** The digest of a case holds a secret, so no request leaves the process
- **THEN** The counter adds one count for that point with `error` equal to `secret`

#### Scenario: An error that no class names
- **WHEN** The decision model raises `RuntimeError` inside the chain
- **THEN** The counter adds one count for that point with `error` equal to `other`

### Requirement: The record holds the dated model that answered
The decision record SHALL hold the model name that the decision model answered with, so the record names the dated snapshot that served the request. The record SHALL hold the configured model name only when the answer names no model.

#### Scenario: A reply names its dated model
- **WHEN** The decision model answers with the model name `typesafe/jev-1.14-20261014`
- **THEN** The record holds that dated name, not the configured name

### Requirement: A cuts file of another model gives the fallback
The chain SHALL load the cuts of a point before it sends the request. When the `model` of the cuts file differs from the model target of `ai.decision_model`, which is the name after a provider prefix such as `litellm:` or the whole name when it has no prefix, the chain SHALL give the fallback with the band `none`, SHALL send no request, and SHALL add one count with `error` equal to `model_mismatch` to the failed counter.

#### Scenario: Cuts of model A, model B in use
- **WHEN** The cuts file names `typesafe/jev-1.13` and `ai.decision_model` names `typesafe/jev-1.14`
- **THEN** The decision is the fallback with the band `none`, no request reaches the model, and the failed counter adds one count with `error` equal to `model_mismatch`

#### Scenario: A gateway route of the model of the cuts
- **WHEN** The cuts file names `typesafe/jev-1.14` and `ai.decision_model` names the gateway route `litellm:typesafe/jev-1.14`
- **THEN** The model answers, and the cuts give the band
