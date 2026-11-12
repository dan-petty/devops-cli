# roadmap-stage-findings Specification

## Purpose
Defines how the stage job keeps each problem of a refused plan reply as a finding with its gate and code, so that each return and each code can be counted.

## Requirements

### Requirement: The stage checks give each problem as a finding with its gate and code
The stage job SHALL keep each problem of a refused reply as a finding with its gate, its code, the path of its message and its text. The code SHALL be the key of the `MESSAGES.roadmap` message that the text matches, or `uncoded`. The model SHALL get the texts of the findings in order, joined by one space, and the refused file SHALL keep the findings of each reply.

#### Scenario: A reply that two gates refuse
- **WHEN** the gates `paths` and `what-changes` refuse each reply of a plan
- **THEN** each reply of the refused file holds two findings with these gates and their codes, and the return sends their texts joined by one space

#### Scenario: Each gate message has its own code
- **WHEN** a test fills the fields of each message of `MESSAGES.roadmap` whose key starts with `stage_problem_`
- **THEN** the finding of that text has the key of that message as its code

### Requirement: Each return logs the counts of its findings
Each reply after a return SHALL log `stage gate findings` with the findings of the reply before it and the counts gone, stuck and new, where stuck is the same gate and the same text with the digits masked. The line `stage gate returns` SHALL name the gates and codes of the last refused reply. Each reply that the checks judge SHALL observe its count of findings in `devops_cli_roadmap_stage_gate_problems` by `repo` and `reply`.

#### Scenario: A reply that stays refused
- **WHEN** the checks refuse a plan with two findings, and then refuse each of its 3 returns with one of them
- **THEN** three `stage gate findings` lines give return 1 with in 2, gone 1, stuck 1 and new 0, and returns 2 and 3 with in 1 and stuck 1, and the `stage gate returns` line names the gate `paths` and its code

#### Scenario: A pass after a return
- **WHEN** the first reply has two findings and the reply after the return passes the checks
- **THEN** the histogram holds one observation of 2 for reply 0 and one of 0 for reply 1

### Requirement: A data file holds the seed fix class of each code
`stage_finding_classes.json` SHALL hold, for each code of the saved refused replies, its gate, its fix class (`mechanical`, `model_fixable`, `low_share` or `never`), the findings fixed by the next reply, the findings with a next reply, the rate and its Wilson lower bound. The saved refused replies of the test fixture SHALL give the same values.

#### Scenario: The saved replies give the data file
- **WHEN** a test codes each problem of the saved refused replies and counts each code
- **THEN** each problem has a code that is not `uncoded`, and the counts, classes and bounds equal those of the data file
