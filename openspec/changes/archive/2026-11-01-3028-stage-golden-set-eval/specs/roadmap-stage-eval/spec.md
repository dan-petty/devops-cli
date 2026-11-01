## Purpose
The golden set of the stage job: committed cases of plans with their known defects, a replay of them through the deterministic gates, and a live score of a chosen model, so a change of the stage prompt or of the checks has a baseline to beat.

## ADDED Requirements

### Requirement: The golden set holds the plans with their defects
The set SHALL hold one folder under `tests/fixtures/roadmap_eval/stage/` for each case: the issue text, the plan, the facts of the tree that the gates need, and the known defects. It SHALL hold the 37 plans of 2026-11-01 and at least 3 cases with the verdict `good` and no defect. A defect SHALL have a type from the shared enum, the review text with its evidence, and the gate that must refuse it: `paths`, `kind`, `pending` or `none`.

#### Scenario: The set loads
- **WHEN** the set is loaded
- **THEN** it holds at least 40 cases, at least 3 of them `good`, and each defect has one of the nine types

#### Scenario: A case that does not match the model
- **WHEN** a case folder has a defect with a type that is not in the enum
- **THEN** loading fails with an error that names the case

### Requirement: The replay fails when a gate stops refusing a known-bad plan
`devops roadmap eval stage --replay` SHALL run the recorded plan of each case through the gates `paths` and `kind`, with no model call and no read of git. It SHALL exit 1 when a gate no longer refuses a defect that names it, when a gate does not name a path that the defect lists, or when a gate refuses a `good` plan. Otherwise it SHALL exit 0.

#### Scenario: Every gate refuses what it must
- **WHEN** the replay runs on the set
- **THEN** it exits 0 and prints, for each gate, the known defects and the defects it caught

#### Scenario: A gate stops refusing
- **WHEN** a plan of the set holds a missing path and the path is made a file of the recorded tree
- **THEN** the replay exits 1 and names the case and the gate

#### Scenario: A good plan is refused
- **WHEN** a `good` plan is changed to name a path that its tree lacks
- **THEN** the replay exits 1 and names the case

### Requirement: A defect for a gate that does not exist yet is listed, not failed
A defect with the gate `pending` SHALL be listed with its type and the issue of the gate, and SHALL fail nothing. A defect with the gate `none` SHALL be listed as judged by no gate. When a gate exists for the type of a `pending` defect, the replay SHALL fail and say to set the gate of the defect.

#### Scenario: Pending defects
- **WHEN** the replay runs on the set
- **THEN** the output lists the types `false_premise`, `ignores_existing_code`, `spec_delta_wrong`, `verify_form`, `task_order` and `criterion_dropped` with their counts, and the exit code is 0

#### Scenario: A gate arrives
- **WHEN** a `pending` defect has the type of a gate that exists
- **THEN** the replay exits 1 and says that the case file must name the gate

### Requirement: The live run scores the first reply of the model
`devops roadmap eval stage` SHALL plan each case with the stage planner, the model of the `analysis` task or `--model`, and a checkout of the commit of the case. It SHALL judge the first reply with the gates, and print for each defect type that a gate catches the cases that have it, how many the model avoided, how many a gate caught, and the rate, with a total. It SHALL show no rate for a type that no gate judges. It SHALL store the report as JSON under the data directory.

#### Scenario: A reply with a missing path
- **WHEN** the first reply of the model names a file that the checkout lacks, and the second reply is right
- **THEN** the case is `staged`, the first reply counts as caught by `paths` and not as avoided, and the report file holds the model name and the rows

#### Scenario: A reply that passes
- **WHEN** the first reply of the model passes both gates
- **THEN** the case counts as avoided for each type of its known defects that a gate catches

#### Scenario: A model call fails
- **WHEN** the model call fails for a case
- **THEN** the case ends `failed`, counts as not avoided, and the command exits 1 after the other cases

### Requirement: The dry run makes no request
`devops roadmap eval stage --dry-run` SHALL make no request to a model or to git, and SHALL list the cases and the model calls a run makes. The command SHALL carry the dry-run class `request-plan`.

#### Scenario: The dry run
- **WHEN** the command runs with `--dry-run` and `--case` for one case
- **THEN** it exits 0, the model fake records no call, and the output names the case

### Requirement: A group holds the eval commands
The command group `devops roadmap eval` SHALL hold the golden-set commands. The command `stage` SHALL be one of them, with the options `--case`, `--model`, `--limit`, `--json`, `--dry-run` and `--replay`.

#### Scenario: The command is found
- **WHEN** the user runs `devops roadmap eval --help`
- **THEN** the output lists `stage`
