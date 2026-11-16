# Spec Delta

## MODIFIED Requirements

### Requirement: The verify command scores the verification pass
`devops roadmap eval verify` SHALL run the verification pass on the plan of each case of the golden set as an agent with the read-only tools of the stage job, on the checkout of the commit of the case, with the model of the `stage_review` task or `--model`. It SHALL print the recall of the labeled defects (all, and the blocker and major ones), the recall for each type, and the count of findings on the `good` plans, and SHALL store the score as JSON under `.data/`.

#### Scenario: A finding on a good plan
- **WHEN** the verifier returns a finding for a case with the verdict `good`
- **THEN** the score counts one finding on good plans and no defect found

#### Scenario: The report is stored
- **WHEN** the command runs on the set
- **THEN** a JSON file under `.data/roadmap_eval/verify/` holds the model, the recall, the rows and the findings of each case

### Requirement: The verify run is the pass of the stage job
The run SHALL give the agent the OpenSpec tool that the stage job gives `read_spec` and the context window of the task `stage_review`, and `--model` SHALL keep the other settings of that task.

#### Scenario: A run reads a spec
- **WHEN** the verifier calls `read_spec` in a run
- **THEN** the tool answers from the specs of the checkout of the case

#### Scenario: The model option keeps the task
- **WHEN** the command runs with `--model` and the task `stage_review` sets a provider
- **THEN** the review runs on that provider with the model of the option
