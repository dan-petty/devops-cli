## ADDED Requirements

### Requirement: The intake outcome counter is declared and documented
`INSTRUMENTS` SHALL hold the counter `devops_cli_roadmap_intake_candidates_total` (unit `1`, attributes `repo` and `result`). The `result` SHALL be `placed`, `duplicate`, `skipped` or `failed`. `docs/TELEMETRY.md` SHALL list the counter. One repository SHALL add 4 series, and the text of the instrument SHALL say "4 series".

#### Scenario: The registry and the document list the counter
- **WHEN** a test reads `INSTRUMENTS` and `docs/TELEMETRY.md`
- **THEN** both list `devops_cli_roadmap_intake_candidates_total`, the registry gives the kind counter with the unit `1`, and the text holds "4 series"

### Requirement: Each intake candidate counts once under its result
`apply_intake` SHALL take the keyword `repo` and SHALL add 1 to `devops_cli_roadmap_intake_candidates_total` for each candidate of the plan, with the attributes `repo` and `result`. A candidate that intake wrote with no possible duplicate SHALL count as `placed`, and one that it wrote with a possible duplicate SHALL count as `duplicate` and not as `placed`.

#### Scenario: Each outcome counts once
- **WHEN** a test runs `apply_intake` over four candidates that give the results `placed`, `duplicate`, `skipped` and `failed`
- **THEN** the counter holds 1 for each result, under the repository of the round

#### Scenario: A possible duplicate is placed
- **WHEN** the model names an Item as the possible original of a candidate
- **THEN** intake places the candidate, and the counter holds 1 for `duplicate` and 0 for `placed`

### Requirement: A candidate that is not written counts as skipped or failed
A candidate with the outcome skip, or whose Item a person changed since the plan, SHALL count as `skipped`. A candidate whose write raised `GitHubOperationError` SHALL count as `failed`. An error for a rate limit or a refused token SHALL go on, and the candidates that it keeps from running SHALL count nothing.

#### Scenario: An Item that a person changed
- **WHEN** a person changes the Item of a candidate between the plan and the write
- **THEN** the counter holds 1 for `skipped` and 0 for `failed`

#### Scenario: A rate limit
- **WHEN** the write of the second of three candidates raises a rate limit error
- **THEN** the error goes on, the counter holds 1 for `placed`, and the third candidate counts nothing

### Requirement: The intake round starts its four series at zero
The intake round SHALL add 0 to `devops_cli_roadmap_intake_candidates_total` for each of the four results of its repository before the first candidate, also when the round writes nothing.

#### Scenario: A round with no candidate
- **WHEN** the intake round runs over a repository with no candidate
- **THEN** the counter holds 0 for each of the four results

#### Scenario: A round with one candidate
- **WHEN** the intake round places one candidate
- **THEN** the counter holds 1 for `placed` and 0 for the other three results

### Requirement: The implement job sends the seconds of its checks, its publish and its watch
The implement job SHALL send one sample of `devops_cli_roadmap_step_seconds` with the attributes `repo`, `row` `implement`, `step` and `result` for each call of the scoped checks (`checks`), for each publish of a branch (`publish`) and for each watch of the checks of the pull request (`watch`). The `result` SHALL be `error` when the step raised an error, and for a watch also when it returns a check that failed; else `ok`.

#### Scenario: A run sends one sample for each step
- **WHEN** a test runs the implement job over a Staged item and over a Planned item with passing checks
- **THEN** the histogram holds one sample for each of `checks`, `publish` and `watch` with `row` `implement` and `result` `ok`

#### Scenario: Scoped checks that no fix repairs
- **WHEN** a scoped check fails after the last fix round
- **THEN** the histogram holds one `checks` sample with `result` `error`, and no `publish` and no `watch` sample

#### Scenario: A failed check of the pull request
- **WHEN** the first watch returns a failed check and the watch after the repair passes
- **THEN** the histogram holds one `watch` sample with `result` `error` and one with `result` `ok`, and two `checks` and two `publish` samples with `result` `ok`

### Requirement: The publish sample excludes the checks and the push of a stop
The `publish` sample SHALL cover only the push and the draft pull request, and SHALL NOT cover the scoped checks. The push of a stop of the job SHALL send no sample.

#### Scenario: Publish excludes the checks
- **WHEN** the scoped checks take 10 seconds and the push takes 2 seconds
- **THEN** the `checks` sample holds at least 10 seconds and the `publish` sample holds less than 10 seconds

### Requirement: The implement series are counted in the text of the instrument
One repository SHALL add 6 series for the implement row (3 steps, 2 results), and the buckets SHALL add none. The text of the instrument SHALL say "6 series", and `docs/TELEMETRY.md` SHALL hold it.

#### Scenario: The text states the series counts
- **WHEN** a test reads the text of the histogram and `docs/TELEMETRY.md`
- **THEN** both hold "6 series" for the implement row and "10 series" for the stage row
