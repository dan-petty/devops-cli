# roadmap-stage/verification Specification

## Purpose
The verification pass that follows the gates of a plan: the defect types of a finding, the repair rounds, the tools of the verifier, and the Jev screen that can skip the model review.

## Requirements

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

### Requirement: A finding has one of the nine defect types
A verification reply SHALL hold findings, and each finding SHALL have a `type` that is one of `missing_path`, `false_premise`, `spec_delta_wrong`, `verify_form`, `task_order`, `criterion_dropped`, `ignores_existing_code`, `contrived_test` and `other`, a place, a problem and a quote. The prompt of the pass SHALL name the same nine types.

#### Scenario: An unknown type
- **WHEN** the verifier names a finding type outside the nine types on both tries
- **THEN** the item stops with the class `StructuredOutputValidationError` and the job opens no pull request

#### Scenario: The prompt and the schema agree
- **WHEN** the prompt of the pass is read
- **THEN** it names each of the nine types and no other type

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

### Requirement: Other findings go into the comment
The job SHALL list each finding that does not return the plan in the comment that names the draft pull request, with its type, place, problem and quote. The text of a finding SHALL be on one line, with a handle, a link or a reference to another repository in a code span. The job SHALL open the draft pull request.

#### Scenario: A contrived test finding
- **WHEN** the verifier returns a `contrived_test` finding
- **THEN** the comment lists the finding and the draft pull request is open

#### Scenario: No finding
- **WHEN** the verifier returns no finding
- **THEN** the comment holds no findings section

### Requirement: The verification prompt names the missing path of a needed file
The verification prompt `src/devops_cli/ai/tasks/roadmap_stage_verify.md` SHALL name `missing_path` for a code change that needs a file that the plan does not change, and SHALL keep the type for a file that does not exist and that no earlier group creates.

#### Scenario: The prompt names the missing path type
- **WHEN** The verification prompt `src/devops_cli/ai/tasks/roadmap_stage_verify.md` is read.
- **THEN** The prompt states that a code change that needs an unchanged file is a `missing_path` finding.

#### Scenario: The prompt keeps the absent-file case
- **WHEN** The verification prompt `src/devops_cli/ai/tasks/roadmap_stage_verify.md` is read.
- **THEN** The prompt states that a file that does not exist and that no earlier group creates is a `missing_path` finding.

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
- **WHEN** the verifier reads `src/devops_cli/roadmap/stage/stage_verify.py` during a run
- **THEN** the trace of the item holds that read, and the comment of the staged item lists the path

### Requirement: The verification prompt separates a dropped criterion from a test-only group that delivers its criterion
The prompt of the verification pass SHALL define `criterion_dropped` for a criterion whose group changes only test files while no group of the plan changes the code or the data that the criterion needs, and SHALL say that a group which changes only test files and tests code of an earlier group is no `criterion_dropped`.

#### Scenario: The prompt names the test-only group
- **WHEN** The prompt of the verification pass is read.
- **THEN** The line of `criterion_dropped` names a group that changes only test files, names the earlier group that changes the code, and says that such a group is no `criterion_dropped`.

### Requirement: A Jev screen may skip the model review of a plan
The screen before the model review of a plan SHALL be the decision point `stage.verify_screen`, with its mode in `roadmap.decisions`. With the mode `on` and `ai.decision_model` set, the stage job SHALL ask the decision model nine yes/no questions about a digest of the input of the review in one request, and SHALL skip the review when no probability reaches its fitted cut. With any other mode or band, or with `ai.decision_model` empty, the review SHALL run.

#### Scenario: The setting is off
- **WHEN** the stage job reviews a plan and `stage.verify_screen` is not in `roadmap.decisions`
- **THEN** the reviewer runs and no request goes to the decision model

#### Scenario: No decision model is configured
- **WHEN** `stage.verify_screen` has the mode `on` and `ai.decision_model` is empty
- **THEN** the reviewer runs, no request goes to the decision model, and the counter `devops_cli_decision_point_total` has no series

#### Scenario: Mode on and the band continue
- **WHEN** the mode is `on` and every probability is under its cut
- **THEN** the reviewer is not called and the plan has no finding

#### Scenario: Mode on and a probability at its cut
- **WHEN** the mode is `on` and one probability is at or above its cut
- **THEN** the reviewer runs

#### Scenario: Mode shadow
- **WHEN** the mode is `shadow`
- **THEN** the reviewer runs, one counter point names the point, the resolver `model`, the band and the mode, and one decision record and one outcome record share an identifier and name the band and the result of the reviewer

### Requirement: The screen fails open
The screen SHALL run the review when the request to the decision model raises an error, times out or leaves a question unanswered, or when the digest holds a secret. It SHALL log the cause and count the resolver `fallback` with the band `none`.

#### Scenario: Jev fails
- **WHEN** the mode is `on` and the request to the decision model `typesafe/jev-1.14` fails with HTTP 503
- **THEN** the reviewer runs, one warning names the error, and the counter counts the resolver `fallback` with the band `none`

### Requirement: The cuts of the screen are fitted data
The cuts of the screen SHALL be read from `jev_screen_cuts.json`, which SHALL hold the Jev model, the day of the fit, the number of cases and the numbers of the check on the other half. The file SHALL have a cut for each question of the screen.

#### Scenario: The data file
- **WHEN** a test loads the cuts of the screen
- **THEN** each of the nine questions has a cut, and the file names the model and the cases of its fit

#### Scenario: MODIFIED of an unknown requirement
- **WHEN** a MODIFIED block names a requirement that the base spec does not hold
- **THEN** the block is unchanged and the validation problem still reaches the model

### Requirement: A refused revision of a repair round returns
A revision of a repair round that the checks refuse SHALL go back to the planner with the refused revision as `previous` and the problem as `problem`, `roadmap.stage.gate_returns` times (default 3) for each repair round, as a refused first reply does. A revision that the checks accept SHALL cause no extra planner call. A revision that is a placeholder in every text SHALL end the item with no return.

#### Scenario: The first revision is refused and the second passes
- **WHEN** the checks refuse the first revision of a repair round and accept the second
- **THEN** the planner gets a third request with `previous` set to the refused revision and `problem` set to the problem of the checks, and the job stages the second revision

#### Scenario: The returns follow the setting
- **WHEN** `roadmap.stage.gate_returns` is 2 and the checks refuse each revision of a repair round
- **THEN** the planner gets two returns for the round and no third

#### Scenario: The revision passes
- **WHEN** the checks accept the first revision of a repair round
- **THEN** the planner gets no return for the round

### Requirement: A revision that stays refused ends the item and is kept
When the checks refuse the revision of a repair round after its last return, the item SHALL fail with a text that names the review and the problem, the planner SHALL make no further request, and `<n>.refused.json` SHALL hold each refused reply of the item with its problem, the refused revisions included.

#### Scenario: Both revisions are refused
- **WHEN** the checks refuse the revision and each returned revision of a repair round
- **THEN** the item fails, the planner has made five requests, and the failure text holds the problem of the last refusal

#### Scenario: The file holds the earlier replies
- **WHEN** the checks refuse the first reply, accept the reply after the return, and refuse each revision of the repair round
- **THEN** the file `1.refused.json` holds the refused first reply and each refused revision, each with its problem

### Requirement: Every open finding returns the plan to the planner
Each open finding of a review SHALL return the plan to the planner while a repair round remains, with each open finding of the review in `problem`. An open finding is a quoted finding of an open type (`OPEN_TYPES`: `missing_path`, `false_premise`, `ignores_existing_code`, `task_order`, `verify_form`, `spec_delta_wrong` or `criterion_dropped`), or a finding that reports a placeholder that the request holds.

#### Scenario: A quoted dropped criterion finding returns the plan
- **WHEN** the verifier returns a `criterion_dropped` finding whose quote is in the issue, and the review of the revised plan finds nothing
- **THEN** the planner gets a second request with the finding in `problem` and the first plan as `previous`, and the staged change holds the revised plan and no open finding

#### Scenario: A quoted spec delta finding returns the plan
- **WHEN** the verifier returns a `spec_delta_wrong` finding whose quote is in the issue, and the review of the revised plan finds nothing
- **THEN** the planner gets a second request with the finding in `problem`, and the staged change holds no open finding

#### Scenario: A placeholder finding returns the plan
- **WHEN** the verifier returns a finding that reports a placeholder that the issue holds, and the review of the revised plan finds nothing
- **THEN** the planner gets a second request with the finding in `problem`, and the staged change holds no open finding

### Requirement: The planner prompt tells how to fix a returned finding
The planner prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL say that `problem` can list the open findings of a model review, and SHALL tell the planner how to fix a `criterion_dropped` finding and a `spec_delta_wrong` finding.

#### Scenario: The planner prompt tells how to fix the two types
- **WHEN** the planner prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` is read
- **THEN** it names the open findings of a model review, `criterion_dropped` and `spec_delta_wrong` in the text that explains `problem`
