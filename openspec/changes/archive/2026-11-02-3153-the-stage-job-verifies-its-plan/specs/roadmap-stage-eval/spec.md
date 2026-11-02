## ADDED Requirements

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
