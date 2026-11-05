# Spec Delta

## MODIFIED Requirements

### Requirement: The verify command scores the verification pass
`devops roadmap eval verify` SHALL run the verification pass on the plan of each case of the golden set as an agent with the read-only tools of the toolset `roadmap.stage.toolset`, on the checkout of the commit of the case, with the OpenSpec tool that the stage job gives `read_spec`, with the context window of the task `verification`, and with the model of the `verification` task or `--model`. `--model` SHALL keep the other settings of that task. It SHALL print the recall of the labeled defects (all, and the blocker and major ones), the recall floor `CONST_ROADMAP_VERIFY_RECALL_FLOOR` with whether the recall of the blocker and major ones meets it, the recall for each type, and the count of findings on the `good` plans, and SHALL store the score as JSON under `.data/`.

#### Scenario: A finding on a good plan
- **WHEN** the verifier returns a finding for a case with the verdict `good`
- **THEN** the score counts one finding on good plans and no defect found

#### Scenario: The report is stored
- **WHEN** the command runs on the set
- **THEN** a JSON file under `.data/roadmap_eval/verify/` holds the model, the recall, the rows and the findings of each case

#### Scenario: The report states the floor
- **WHEN** the command runs on the set
- **THEN** the report states the floor of 90 percent of the blocker and major defects and whether the recall of those defects reaches it

#### Scenario: A run reads a spec
- **WHEN** the verifier calls `read_spec` in a run
- **THEN** the tool answers from the specs of the checkout of the case

#### Scenario: The model option keeps the task
- **WHEN** the command runs with `--model` and the task `verification` sets a provider
- **THEN** the review runs on that provider with the model of the option

### Requirement: The verify command fails on a failed call and has a dry run
The command SHALL end a case whose model call fails as `failed`, count it as no defect found, run the other cases, and exit 1. `--dry-run` SHALL make no request to a model or to git and SHALL list the cases and the one agent run for each. The command SHALL carry the dry-run class `request-plan`.

#### Scenario: A model call fails
- **WHEN** the model call fails for one case
- **THEN** that case ends `failed`, the other cases run, and the command exits 1

#### Scenario: The dry run
- **WHEN** the command runs with `--dry-run` and `--case` for one case
- **THEN** it exits 0, the model fake records no call, and the output names the case
