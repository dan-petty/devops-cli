## ADDED Requirements

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
Each failed request of a point SHALL add one to the counter `devops_cli_decision_point_failed_total`, with the labels `point` and `error`. The value of `error` SHALL be one of `timeout`, `model_error`, `parse`, `secret`, `no_cuts` or `other`, so a point SHALL add at most 6 series to the counter.

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

## MODIFIED Requirements

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

### Requirement: The registry bounds the series of its catalogue
The registry SHALL refuse a catalogue of points whose label sets of `devops_cli_decision_point_total` are more than 92, the bound of ADR 0020 section 7 that `CONST_ROADMAP_DECISION_POINT_MAX_SERIES` holds. A point SHALL list the label sets that it can write: the bands `continue`, `review` and `flag` for each resolver that it has besides the fallback, and `none` for the fallback, in the modes `shadow` and `on`.

#### Scenario: Too many points
- **WHEN** A test builds a catalogue whose label sets are more than `CONST_ROADMAP_DECISION_POINT_MAX_SERIES`
- **THEN** The registry raises an error that names the bound that the constant holds

#### Scenario: The catalogue at the bound
- **WHEN** A test builds a registry whose label sets are exactly `CONST_ROADMAP_DECISION_POINT_MAX_SERIES`
- **THEN** The registry loads and its series count equals the constant

### Requirement: A point fails back
A point SHALL fall back to the current behavior when the decision model raises an error, times out, leaves a question unanswered, answers with a confidence under the floor of the cuts, or when the digest holds a secret. It SHALL give the fallback for every error of the chain, including an error that no class names, and SHALL NOT raise that error to the caller. The registry SHALL log the cause and SHALL count the case with the resolver `fallback` and the band `none`.

#### Scenario: The model fails
- **WHEN** The fake decision model raises an error
- **THEN** The current behavior runs, one log record names the error, and the counter has one increment with the resolver `fallback`

#### Scenario: An error that no class names
- **WHEN** The fake decision model raises `RuntimeError` inside the chain
- **THEN** The decision is the fallback with the band `none`, no error reaches the caller, and the failed counter adds one count with `error` equal to `other`
