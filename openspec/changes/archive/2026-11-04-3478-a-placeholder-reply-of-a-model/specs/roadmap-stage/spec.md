## ADDED Requirements

### Requirement: The stage reply has no return path
The reply schema of the stage job SHALL hold no key `premise_failed`, and SHALL require the keys `summary`, `pull_request_body`, `why`, `what_changes`, `skip_specs`, `feasibility`, `existing_tool` and `groups`. A reply that breaks the schema SHALL go back to the model once, and a second such reply SHALL fail the item with no change to its Status and no comment. The job SHALL have no outcome that returns an item to New.

#### Scenario: A reply with only premise_failed
- **WHEN** a reply is `{"premise_failed": "x"}`
- **THEN** the schema refuses it and names the key `premise_failed` as unknown

#### Scenario: A filler value of premise_failed
- **WHEN** a reply sets `premise_failed` to each of `placeholder`, `x`, `none`, `probe`, `__PROBE__` and "Not yet: I need to inspect the repository first." and holds a valid plan
- **THEN** the schema refuses each reply, and the job does not return the item

#### Scenario: A premise text that states the premise holds
- **WHEN** a reply sets `premise_failed` to the text of #3193, #3109 or #3255, and #3109 quotes a probe line
- **THEN** the schema refuses each reply, and the job does not return the item

#### Scenario: A reply with no plan
- **WHEN** a reply is `{}`
- **THEN** the schema refuses it and names each missing key

#### Scenario: The job returns no item
- **WHEN** the job plans an item and the model answers with a refused reply twice
- **THEN** the item fails, its Status is unchanged, and the job writes no comment on it

### Requirement: A placeholder text is one rule
`is_placeholder` SHALL be true for the texts `x`, `y`, `probe`, `placeholder` and `none`, for `__PROBE__`, and for a text that starts with "Not yet:", with no case and no punctuation around the text. `ReplyText` SHALL apply that rule as a validator and SHALL raise the error type `placeholder_text`.

#### Scenario: The filler words
- **WHEN** `is_placeholder` reads `x`, `y`, `probe`, `__PROBE__`, `placeholder` and `none`
- **THEN** it is true for each

#### Scenario: The refusal of a task
- **WHEN** `is_placeholder` reads "Not yet: I need to inspect the repository first."
- **THEN** it is true

#### Scenario: A real text
- **WHEN** `is_placeholder` reads "The probe shows the path" and "x-ray the cache"
- **THEN** it is false for both

## MODIFIED Requirements

### Requirement: The prompt asks feasibility to quote the probes
The prompt of the stage job SHALL tell the model that `probes` holds the result of read-only commands at the staging commit, SHALL ask `feasibility` to quote the lines of `probes` that confirm the premise, and SHALL tell the model that the reply has no key to report a false premise: when the issue cannot be built as written, `feasibility` says so with the evidence and the plan holds no code that compensates for it.

#### Scenario: The prompt names the probes
- **WHEN** the stage prompt loads
- **THEN** it names `probes`, asks `feasibility` to quote the probes, and does not name `premise_failed` as a key to set

### Requirement: Each item of a stage round counts once by its result
A stage round, whether the Service or the command runs it, SHALL add 1 to `devops_cli_roadmap_stage_total` for each item it handled, with the label `result`: `staged` for an item written as a branch and a draft, `needs_split` for an item stopped on a group over the budget, `failed` for an item that failed in the plan or in the writes, and `skipped` for an item the job left out with a reason. An item SHALL count under one result.

#### Scenario: Four results in one round
- **WHEN** a round stages one item, stops one on the budget, fails one in the model call, and leaves one out for an open dependency
- **THEN** the counter has one point each for `staged`, `needs_split`, `failed` and `skipped`

#### Scenario: A returned item
- **WHEN** a round plans one item and the model answers with the key `premise_failed` twice
- **THEN** the item counts as `failed`, and the counter has no point for `returned`

#### Scenario: A plan with no write
- **WHEN** `devops roadmap stage --plan` runs
- **THEN** the counter has no point

## REMOVED Requirements

### Requirement: A false premise returns the item
**Reason**: A reply with the key `premise_failed` returned 33 items on filler text and 3 items on text that states the premise holds. The return path is removed (#3478).
**Migration**: A person returns an item with `devops roadmap return`. The plan states an issue that cannot be built as written in `feasibility`.
