## ADDED Requirements

### Requirement: The step seconds histogram and the gate refusal counter are declared and documented
`INSTRUMENTS` SHALL hold the histogram `devops_cli_roadmap_step_seconds` (unit `s`, attributes `repo`, `row`, `step`, `result`) and the counter `devops_cli_roadmap_stage_gate_refusals_total` (unit `1`, attributes `repo`, `gate`). `docs/TELEMETRY.md` SHALL list both. One repository SHALL add at most 10 series to the histogram for the stage row (5 steps, 2 results) and 15 to the counter (one for each `ProposalGate`). The buckets SHALL add none.

#### Scenario: The registry and the document list both instruments
- **WHEN** a test reads `INSTRUMENTS` and `docs/TELEMETRY.md`
- **THEN** both list `devops_cli_roadmap_step_seconds` and `devops_cli_roadmap_stage_gate_refusals_total`, and the registry gives the kind histogram with the unit `s` and the kind counter with the unit `1`

#### Scenario: The instrument texts state the series counts
- **WHEN** a test reads the description of each instrument
- **THEN** the histogram text holds "10 series" and the counter text holds the number of members of `ProposalGate` and the word "series"

### Requirement: Each step of a stage round adds its seconds
A stage round SHALL send one sample of `devops_cli_roadmap_step_seconds` for each call of a step, with the attributes `repo`, `row` `stage`, `step` and `result`. The `step` SHALL be `select`, `plan`, `gate`, `review` or `apply`. The `result` SHALL be `error` when the step raised an error, else `ok`: a plan that a gate refuses is `ok`. A job with no review call sends no `review` sample, and a replay of the golden set, which has no repository, sends none.

#### Scenario: A round plans, reviews and writes one item
- **WHEN** a round plans one item whose planner call takes 3 seconds and whose review takes 2 seconds, and the writer writes the item
- **THEN** the collector receives one sample for each of `select`, `plan`, `gate`, `review` and `apply` with `row` `stage` and `result` `ok`, the `plan` sample holds 3 seconds, and the `review` sample holds 2 seconds

#### Scenario: A refused reply
- **WHEN** a gate refuses the first reply and the second reply passes
- **THEN** the item adds two `plan` samples and two `gate` samples, and every `gate` sample has the result `ok`

#### Scenario: A step raises
- **WHEN** the planner call takes 3 seconds and then raises an error
- **THEN** the collector receives a `plan` sample of 3 seconds with `result` `error`, and no sample for a later step

#### Scenario: A write fails
- **WHEN** the writer fails to open the pull request of an item
- **THEN** the collector receives an `apply` sample with `result` `error`

#### Scenario: A replay of the golden set
- **WHEN** `plan_item` plans one item with no repository
- **THEN** the collector receives no step sample and no refusal

### Requirement: Each gate that refuses a reply adds one to the gate refusal counter
The stage planner SHALL add 1 to `devops_cli_roadmap_stage_gate_refusals_total` for each gate of `check_gates` that finds a problem in a reply, with the attributes `repo` and `gate`. The `gate` SHALL be the value of a `ProposalGate` member. A gate that finds several problems in one reply SHALL add 1. A gate that finds none SHALL add nothing.

#### Scenario: One gate refuses
- **WHEN** a reply changes two files that do not exist and the next reply passes every gate
- **THEN** the counter holds 1 for the gate `paths` and no point for any other gate

#### Scenario: A plan passes every gate
- **WHEN** the first reply passes every gate
- **THEN** the counter has no point

#### Scenario: A gate refuses two replies
- **WHEN** the same gate refuses the first reply and the reply that answers it
- **THEN** the counter holds 2 for that gate
