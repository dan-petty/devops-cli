# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: An evidence-backed finding returns the plan once`
- TO: `### Requirement: An evidence-backed finding returns the plan at most twice`

## MODIFIED Requirements

### Requirement: A verification pass follows the gates
When the caller gives a verifier, the planner SHALL run one verification for each plan after the plan passes `check_proposal` and `validate_change`, and before the job opens the draft pull request. The verifier SHALL be an agent of the task slot `ai.tasks.verification` with the read-only tools of the toolset `roadmap.stage.toolset`. Its request SHALL hold the issue, the plan and the capped start of each file that the plan cites. The pass SHALL NOT merge a pull request or mark one ready.

#### Scenario: A plan that passes the gates
- **WHEN** a plan passes the gates and the verifier finds nothing
- **THEN** the verifier runs once with a request that holds the issue, the plan and the cited files, and no message of the planner, and the job opens the draft pull request

#### Scenario: A long cited file
- **WHEN** a plan cites a file with more tokens than `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS`
- **THEN** the request holds only the first tokens of that file

#### Scenario: A plan that fails the gates
- **WHEN** the gates refuse a plan twice
- **THEN** the verifier gets no request

#### Scenario: No pull request is merged or marked ready
- **WHEN** the pass ends with findings
- **THEN** the draft pull request stays a draft and the job makes no merge call

### Requirement: An evidence-backed finding returns the plan at most twice
A finding of type `missing_path`, `false_premise`, `ignores_existing_code`, `task_order` or `verify_form` whose quote is in the issue, the plan, a cited file or a tool answer of the run SHALL return the plan to the planner, with each open finding of the round as the problem. The revised plan SHALL pass the gates and the verification again, at most `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS` times, which is two.

#### Scenario: A false premise with a quote
- **WHEN** the verifier returns a `false_premise` finding whose quote is in the issue
- **THEN** the planner gets a second request with the finding as `problem` and the first plan as `previous`, and the job opens the draft pull request with the revised plan

#### Scenario: A quote that is not in the input
- **WHEN** the verifier returns a `false_premise` finding whose quote is in none of the issue, the plan, the cited files and the tool answers of the run
- **THEN** the planner gets no second request and the finding goes into the comment

#### Scenario: The revised plan has a finding too
- **WHEN** the first revised plan gets a `missing_path` finding with a quote
- **THEN** the planner gets a second repair request with the finding as `problem`

#### Scenario: A task order finding returns the plan
- **WHEN** the verifier returns a `task_order` finding whose quote is in the plan
- **THEN** the planner gets a second request with the finding as `problem`

#### Scenario: A quote from a tool answer
- **WHEN** the verifier reads a line past the cap of a cited file with a tool, and returns an `ignores_existing_code` finding that quotes that line
- **THEN** the planner gets a repair request with the finding as `problem`

### Requirement: An open finding keeps the plan in draft
When the last review of a plan returns a finding that has a quote in its input or in a tool answer of the run and a defect type of `missing_path`, `false_premise`, `ignores_existing_code`, `task_order`, `verify_form` or `spec_delta_wrong`, or a finding that reports a placeholder with a quote in its request, the stage SHALL keep the plan pull request in draft, apply the label `plan/needs-fix` to it, and put those findings at the top of the stage comment.

#### Scenario: A placeholder finding from a fake client
- **WHEN** The fake verification client returns a placeholder finding whose quote is in the input.
- **THEN** The plan pull request is a draft, it holds the label `plan/needs-fix`, and its stage comment starts with the finding text.

#### Scenario: A clean review stages as today
- **WHEN** The fake verification client returns no finding with a quote in the input and an open defect type.
- **THEN** The stage opens the plan pull request as today and applies no `plan/needs-fix` label.

#### Scenario: A later clean round clears the label
- **WHEN** A stage round verifies a plan that holds `plan/needs-fix` and returns no open finding.
- **THEN** The stage removes the label from the pull request.

#### Scenario: An open task order finding
- **WHEN** The last review returns a `task_order` finding whose quote is in the input.
- **THEN** The plan pull request is a draft and it holds the label `plan/needs-fix`.

#### Scenario: A placeholder only in a tool answer
- **WHEN** The verifier reports a placeholder whose quote is in a tool answer and not in its request.
- **THEN** The finding is not open.

## ADDED Requirements

### Requirement: The verification request fits the window of its task
The request and the run of the verifier SHALL use the context window of the task `verification`. With its instructions, the request SHALL stay `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS` tokens below the point where the run offers no more tools.

#### Scenario: A request that does not fit the window
- **WHEN** the cited files of a plan do not fit the limit of the window of the task `verification`
- **THEN** the request keeps the cited files in plan order up to that limit, and drops the others

#### Scenario: A full request gets the tools
- **WHEN** the window of the task `verification` is 65536 tokens and a plan cites more files than fit
- **THEN** the first request of the run is offered the read tools

#### Scenario: The two tasks have different windows
- **WHEN** the task `stage` has a window of 262144 tokens and the task `verification` a window of 12000 tokens
- **THEN** the request of the verifier and the tool limit of its run follow the window of 12000 tokens

### Requirement: The comment lists every finding of each repair round
After the last repair round, the plan SHALL keep each open finding of the last review, and the comment SHALL list every finding of each round.

#### Scenario: The second repair round still has a finding
- **WHEN** the plan still has a return finding after the second repair round
- **THEN** the planner makes no further request, the job keeps the draft with the label `plan/needs-fix`, and the issue receives a comment with the findings

#### Scenario: The comment lists each repair round
- **WHEN** the verifier returns a return finding on each of the first two reviews, and no finding on the third
- **THEN** the planner makes two repair requests, and the comment of the item lists the two return findings

#### Scenario: A mixed first round
- **WHEN** the first review returns a `false_premise`, a `spec_delta_wrong` and a `contrived_test` finding with quotes, and the second review finds nothing
- **THEN** the planner gets the `false_premise` and the `spec_delta_wrong` finding, the comment lists all three, and no finding is open

### Requirement: The verifier reads the repository with the read-only tools
The verifier SHALL check the paths, the premise, the scope against the criteria, the task order, the spec delta and the verify commands of a plan with the read-only tools of the toolset of the run. It SHALL hold no tool that writes a file or runs a shell command. Each read of a verification run SHALL be recorded in the `RunTrace` of that run, and the comment of the staged item SHALL list each read with its path.

#### Scenario: The tool set of the verifier
- **WHEN** a verification run is built for a checkout and a commit with the toolset `base`
- **THEN** its tools are exactly the nine read tools of the toolset `base`

#### Scenario: A read is listed in the comment
- **WHEN** the verifier reads `src/devops_cli/roadmap/stage_verify.py` during a run
- **THEN** the trace of the item holds that read, and the comment of the staged item lists the path

### Requirement: A review run has its own row in the metrics of the tool calls
A verification run SHALL send the metrics of its tool calls with the label `row` value `stage_verify`, and a plan run SHALL keep the value `stage`, so the reads of the verifier do not hide a tool that the planner does not use.

#### Scenario: A verification run calls a tool
- **WHEN** a verification run reads a file
- **THEN** `devops_cli_roadmap_tool_calls_total` holds that call with `row` `stage_verify`, and no point with `row` `stage`

### Requirement: A review run that stops names itself
When a verification run ends with no reply, the failure of the item SHALL name the verification run and SHALL NOT say that no plan was given.

#### Scenario: A verification run hits a limit
- **WHEN** the replies of a verification run pass `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS`
- **THEN** the job raises `RoadmapStageError` with the message of a stopped verification run
