## ADDED Requirements

### Requirement: The rules of the plan check refuse a reply before the push
The stage job SHALL judge each reply with `staged_problems` of the plan check, on the files that it writes for the reply, after `openspec validate`. A reply that the rules refuse SHALL go back to the model as a gate return of the gate `plan-check`, with the line that `devops roadmap plan-check` prints for each problem.

#### Scenario: A group that packs no file goes back to the model
- **WHEN** the first reply has a group that changes `src/devops_cli/sample.py`, which exists, and no code span of its tasks names a file, and the second reply names the file
- **THEN** the job makes two model calls, the second request holds the `group-no-files` line of the plan check as its problem, the job stages the second reply, and the attempt counts 1 gate return

### Requirement: A plan that the plan check refuses is never pushed
A reply that the rules of the plan check still refuse after the last return SHALL fail the item with the class `plan_defect`. The job SHALL push no branch and open no pull request for it.

#### Scenario: The rules refuse each return
- **WHEN** each reply has a group that changes `src/devops_cli/sample.py` and no code span of its tasks names a file
- **THEN** the item fails with the class `plan_defect` and a reason that names `group-no-files`, and `origin` holds no branch but `main`
