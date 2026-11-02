# roadmap-stage-eval Specification

## Purpose
The golden set of the stage job: committed cases of plans with their known defects, a replay of them through the deterministic gates, and a live score of a chosen model, so a change of the stage prompt or of the checks has a baseline to beat.

## Requirements

### Requirement: The golden set holds the plans with their defects
The set SHALL hold one folder under `tests/fixtures/roadmap_eval/stage/` for each case: the issue text, the plan, the facts of the tree, and the known defects. It SHALL hold the 37 plans of 2026-11-01 and at least 3 `good` cases with no defect. A defect SHALL have a type from the shared enum, the review text with its evidence, and the gate that must refuse it: `paths`, `kind`, `pending` or `none`. A defect with the gate `none` and a type that a gate catches SHALL give a `reason`.

#### Scenario: The set loads
- **WHEN** the set is loaded
- **THEN** it holds at least 40 cases, at least 3 of them `good`, and each defect has one of the nine types

#### Scenario: A case that does not match the model
- **WHEN** a case folder has a defect with a type that is not in the enum
- **THEN** loading fails with an error that names the case

#### Scenario: A defect that no gate can judge says why
- **WHEN** the set is loaded
- **THEN** each defect of the types `ignores_existing_code`, `spec_delta_wrong`, `verify_form` and `task_order` that has the gate `none` has a `reason`, and each of them that has the gate `paths` holds the `message` of the problem

### Requirement: The replay fails when a gate stops refusing a known-bad plan
`devops roadmap eval stage --replay` SHALL run the recorded plan of each case through the gates `paths`, `kind` and `criteria`, with no model call and no read of git. The gate `paths` SHALL be `check_proposal` with the capabilities of the case, so it judges `missing_path`, `spec_delta_wrong` and `verify_form`. It SHALL exit 1 when a gate no longer refuses a defect that names it, does not give the path or message that the defect lists, or refuses a `good` plan. Otherwise it SHALL exit 0.

#### Scenario: Every gate refuses what it must
- **WHEN** the replay runs on the set
- **THEN** it exits 0 and prints, for each gate, the known defects and the defects it caught

#### Scenario: A gate stops refusing
- **WHEN** a plan of the set holds a missing path and the path is made a file of the recorded tree
- **THEN** the replay exits 1 and names the case and the gate

#### Scenario: A rule of the spec delta stops refusing
- **WHEN** the rule for a spec delta that the changed paths do not need refuses nothing
- **THEN** the replay exits 1 and names the case and the type `spec_delta_wrong`

#### Scenario: A good plan is refused
- **WHEN** a `good` plan is changed to name a path that its tree lacks
- **THEN** the replay exits 1 and names the case

### Requirement: A defect for a gate that does not exist yet is listed, not failed
A defect with the gate `pending` SHALL be listed with its type and the issue of the gate, and SHALL fail nothing, for a type in `PENDING_GATES`. A defect with the gate `none` SHALL be counted as judged by no gate. When a gate exists for the type of a `pending` defect, or no gate is planned for it, the replay SHALL fail and say to set the gate of the defect. The list of types that wait for a gate SHALL print only when a type waits.

#### Scenario: Pending defects
- **WHEN** the replay runs on the set
- **THEN** the output has no list of types that wait for a gate, and the exit code is 0

#### Scenario: A false premise is judged by no gate
- **WHEN** the replay runs on the set
- **THEN** the defects of the type `false_premise` are counted as judged by no gate, and the exit code is 0

#### Scenario: A gate arrives
- **WHEN** a `pending` defect has the type of a gate that exists
- **THEN** the replay exits 1 and says that the case file must name the gate

### Requirement: The live run scores the first reply of the model
`devops roadmap eval stage` SHALL plan each case with the stage planner, the model of the `analysis` task or `--model`, and a checkout of the commit of the case. It SHALL judge the first reply with the gates, and print for each scored defect type the cases that have it, how many the model avoided, how many a gate caught, and the rate, with a total. It SHALL show no rate for a type that no gate judges, nor for the gate `kind`. It SHALL store the report as JSON under the data directory.

#### Scenario: A reply with a missing path
- **WHEN** the first reply of the model names a file that the checkout lacks, and the second reply is right
- **THEN** the case is `staged`, the first reply counts as caught by `paths` and not as avoided, and the report file holds the model name and the rows

#### Scenario: A reply that passes
- **WHEN** the first reply of the model passes both gates
- **THEN** the case counts as avoided for each type of its known defects that the live run scores

#### Scenario: The kind gate
- **WHEN** the score is printed
- **THEN** the `kind` row shows its count and no rate, since the client sends a reply that breaks the schema back unseen

#### Scenario: The model breaks the schema twice
- **WHEN** the model breaks the schema of the reply on both tries
- **THEN** the case ends `failed` and counts as neither avoided nor caught

#### Scenario: A model call fails
- **WHEN** the model call fails for a case
- **THEN** the case ends `failed`, counts as not avoided, and the command exits 1 after the other cases

### Requirement: The dry run makes no request
`devops roadmap eval stage --dry-run` SHALL make no request to a model or to git, and SHALL list the cases and the model calls a run makes. The command SHALL carry the dry-run class `request-plan`.

#### Scenario: The dry run
- **WHEN** the command runs with `--dry-run` and `--case` for one case
- **THEN** it exits 0, the model fake records no call, and the output names the case

### Requirement: A group holds the eval commands
The command group `devops roadmap eval` SHALL hold the golden-set commands. The command `stage` SHALL be one of them, with the options `--case`, `--model`, `--limit`, `--json`, `--dry-run`, `--replay` and `--no-toolbox`.

#### Scenario: The command is found
- **WHEN** the user runs `devops roadmap eval --help`
- **THEN** the output lists `stage`

### Requirement: The live run plans with the toolbox unless told not to
`devops roadmap eval stage` SHALL plan each case with the toolbox of the stage job. With `--no-toolbox` it SHALL plan each case with one model call and no tool. Both modes SHALL print the same table and store a report of the same shape, so two runs of one model compare.

#### Scenario: The default run
- **WHEN** a live run plans a case with a scripted model that calls `read_file` once and then answers
- **THEN** the model gets the tool, and the case counts as before

#### Scenario: Without the toolbox
- **WHEN** the run has `--no-toolbox`
- **THEN** the model gets one request with no tool, and the table has the same rows

### Requirement: The verify command scores the verification pass
`devops roadmap eval verify` SHALL run the verification pass on the plan of each case of the golden set, with the cited files read from the checkout of the commit of the case, and the model of the `verification` task or `--model`. It SHALL print the recall of the labeled defects (all, and the blocker and major ones), the recall for each type, and the count of findings on the `good` plans, and SHALL store the score as JSON under `.data/`.

#### Scenario: A finding on a good plan
- **WHEN** the verifier returns a finding for a case with the verdict `good`
- **THEN** the score counts one finding on good plans and no defect found

#### Scenario: The report is stored
- **WHEN** the command runs on the set
- **THEN** a JSON file under `.data/roadmap_eval/verify/` holds the model, the recall, the rows and the findings of each case

### Requirement: A finding matches one labeled defect of its type
The score SHALL match each finding to at most one labeled defect of the same type, the most serious defect first. The recall SHALL be the matched defects over the labeled defects.

#### Scenario: A finding that matches a defect
- **WHEN** the verifier returns one `false_premise` finding for a case that has two labeled `false_premise` defects and one `missing_path` defect
- **THEN** the score counts 1 of 3 defects found, 1 of 2 for `false_premise` and 0 of 1 for `missing_path`

### Requirement: The verify command fails on a failed call and has a dry run
The command SHALL end a case whose model call fails as `failed`, count it as no defect found, run the other cases, and exit 1. `--dry-run` SHALL make no request to a model or to git and SHALL list the cases and the one call for each. The command SHALL carry the dry-run class `request-plan`.

#### Scenario: A model call fails
- **WHEN** the model call fails for one case
- **THEN** that case ends `failed`, the other cases run, and the command exits 1

#### Scenario: The dry run
- **WHEN** the command runs with `--dry-run` and `--case` for one case
- **THEN** it exits 0, the model fake records no call, and the output names the case

### Requirement: The group lists the verify command
The command group `devops roadmap eval` SHALL list `verify`, with the options `--case`, `--model`, `--limit`, `--json`, `--dry-run`, `--cases` and `--source`.

#### Scenario: The command is found
- **WHEN** the user runs `devops roadmap eval --help`
- **THEN** the output lists `verify`

### Requirement: The replay counts the defects by type
The replay SHALL print, for each type of defect that the set holds, the defects a gate caught, the defects it missed, the defects that wait for a gate, the defects that no gate judges, and the total. It SHALL then print the share of all known defects that a gate judges, caught or missed. The JSON report SHALL hold the same counts and the number of defects judged and known.

#### Scenario: The counts by type
- **WHEN** the replay runs on the set
- **THEN** it prints a row for each type, with `verify_form` caught 4, missed 0 and judged by no gate 12, and the line `Defects that a gate judges: 64 of 299 (21%).`

#### Scenario: The counts as JSON
- **WHEN** the replay runs with `--json`
- **THEN** the report holds `defects` with `judged` 64 and `known` 299, and a row for each type
