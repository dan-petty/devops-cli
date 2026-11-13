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

### Requirement: An evidence-backed finding returns the plan for the set repair rounds
A finding of type `missing_path`, `false_premise`, `ignores_existing_code`, `task_order`, `verify_form`, `spec_delta_wrong` or `criterion_dropped` that quotes its input or a tool answer of the run, on a place of the plan or the issue, SHALL return the plan to the planner with each open finding of the round as the problem. The revision SHALL pass the gates and the review again, at most `roadmap.stage.verify_repair_rounds` times (two by default), and for each extra round of the extension.

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

#### Scenario: A place that the plan does not hold
- **WHEN** the verifier returns a `false_premise` finding whose quote is in the issue and whose place is a key that the plan does not have
- **THEN** the planner gets no second request and the finding goes into the comment

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
A revision of a repair round that the checks refuse SHALL go back to the planner with the refused revision as `previous` and the problem as `problem`, as a refused first reply does: `roadmap.stage.gate_returns` times (default 3) for each repair round, and the extra return of the item when `roadmap-stage/returns` grants it (#4851). A revision that the checks accept SHALL cause no extra planner call. A revision that is a placeholder in every text SHALL end the item with no return.

#### Scenario: The first revision is refused and the second passes
- **WHEN** the checks refuse the first revision of a repair round and accept the second
- **THEN** the planner gets a third request with `previous` set to the refused revision and `problem` set to the problem of the checks, and the job stages the second revision

#### Scenario: The returns follow the setting
- **WHEN** `roadmap.stage.gate_returns` is 2 and the checks refuse each revision of a repair round with the same problem
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

### Requirement: The repair rounds of the review are a setting with a hard ceiling
The setting `roadmap.stage.verify_repair_rounds` SHALL set the repair rounds of the model review, with a default of 2. The setting `roadmap.stage.verify_repair_rounds_ceiling` SHALL set the most repair rounds of an item, with a default of 4. The settings load SHALL refuse a value of `verify_repair_rounds` above `verify_repair_rounds_ceiling` with an error that names both settings, and a value of either setting above 16, 4 times the default of the ceiling.

#### Scenario: The setting sets the rounds
- **WHEN** `roadmap.stage.verify_repair_rounds` is 1 and each review returns the plan
- **THEN** the planner gets 2 requests and the verifier gets 2 requests

#### Scenario: A value over the ceiling
- **WHEN** the settings load reads `roadmap.stage.verify_repair_rounds` of 5 with no ceiling set, or of 17
- **THEN** the load fails with an error that names `verify_repair_rounds`

### Requirement: One more repair round follows while a review fixes more findings than it adds
After the last repair round of the setting, the stage SHALL start one more round only while the last review marked more earlier findings `gone` than it opened new findings, with no model call. No item SHALL get more repair rounds than `roadmap.stage.verify_repair_rounds_ceiling`, and no round SHALL start after the Service stops. Each round past the setting SHALL log `stage review extended:` with the round and the counts of fixed and added findings.

#### Scenario: A review fixes an earlier finding after the last round
- **WHEN** the setting is 2, the first review opens 3 findings, the second review marks each of them `holds`, the third review marks one `gone` and opens no new finding, and the fourth review marks each finding `gone`
- **THEN** the planner gets 4 requests, the staged change holds no open finding, the job logs one `stage review extended:` line with `round=3 fixed=1 added=0`, and the result line counts 4 review runs

#### Scenario: A review fixes as many findings as it adds
- **WHEN** the setting is 2, the first review opens 3 findings, the second review marks one `gone`, and the third review marks one `gone` and opens 1 new finding in the changed text
- **THEN** the planner gets 3 requests, the staged change holds 2 open findings, and the job logs no `stage review extended:` line

#### Scenario: No round past the ceiling
- **WHEN** the setting is 2 and each later review marks one earlier finding `gone` and opens no new finding
- **THEN** the planner gets 1 + `roadmap.stage.verify_repair_rounds_ceiling` requests: 5 at the default ceiling, and 7 when the ceiling is 6

#### Scenario: No round in a drain
- **WHEN** the Service stops during the first review, and the review returns the plan
- **THEN** no repair round starts, the planner gets 1 request, and the item ends with the stop

### Requirement: A later review gets the earlier open findings and the answer
A review that follows a repair SHALL get, beside the issue, the plan and the files, the key `earlier`, which holds each open finding of the review before it with its `number`, `type`, `where`, `problem` and `quote`, and the key `answer`, which holds each block of lines of the plan that the revision added or changed. The task prompt `roadmap_stage_verify_later.md` SHALL follow the prompt of the pass in such a review.

#### Scenario: The request of a repair round
- **WHEN** the first review opens a `false_premise` finding, and the planner answers a revision that changes the `why` of the plan
- **THEN** the second request of the verifier holds the finding in `earlier` with the number 1, and `answer` holds the new `why`

### Requirement: A later review gives a verdict for each earlier finding
The reply of a later review SHALL give one verdict, `holds` or `gone`, for each earlier finding, and the new findings. An earlier finding that the reply marks `holds`, gives no verdict, or reports again as a new finding SHALL stay open. Any other earlier finding that it marks `gone` SHALL be fixed.

#### Scenario: A verdict closes a finding
- **WHEN** the first review opens one finding and the review of the revision marks it `gone` and opens no new finding
- **THEN** the staged change holds no open finding

#### Scenario: No verdict keeps a finding
- **WHEN** the first review opens two findings and the review of the revision gives a verdict only for the first, `gone`
- **THEN** the second finding stays open

#### Scenario: Two verdicts keep a finding
- **WHEN** the review of the revision marks one earlier finding both `gone` and `holds`
- **THEN** the finding stays open

### Requirement: The first review of a plan keeps its request
The first review of a plan SHALL get no `earlier` and no `answer` key, the reply schema with only `findings`, and the prompt of the pass with no text of a later review. So the golden set of `devops roadmap eval verify`, which scores a first review, keeps its request.

#### Scenario: The first review does not change
- **WHEN** the first review of a plan sends its request
- **THEN** the request holds only `number`, `title`, `body`, `plan` and `files`, and the instructions are the prompt of the pass and the rules of the tools

### Requirement: A later review opens a new finding only in changed text
A new finding of a later review SHALL be open only when it is open by the rules of an open finding and its quote, with white space folded, is in a block of `answer`. A new finding on a text that the revision did not change SHALL be advice, which the comment lists. The step SHALL take the blocks of `answer` from a `difflib` diff of the lines of the plan before the repair and of the revision, so a line that the revision moves is changed text.

#### Scenario: A new finding on unchanged text
- **WHEN** a later review opens a `false_premise` finding whose quote is in the issue, and the revision did not change that text
- **THEN** the finding is advice, and it returns no plan

#### Scenario: A new finding on changed text
- **WHEN** a later review opens a `false_premise` finding whose quote is in a line of the plan that the revision added
- **THEN** the finding is open

### Requirement: A finding names its place in the plan or the issue
Each finding of the verification reply SHALL name its place in `where` with a `part` and a `section`. The part SHALL be one of `proposal`, `design`, `tasks`, `spec` and `issue`. The section SHALL be a key or a text of the proposal or the design, the number of a task group, the name of a requirement of the spec delta with its capability in `capability`, or a text of the issue. The comment line of a finding SHALL show the part, the capability when it has one, and the section in brackets.

#### Scenario: A dropped criterion names the criterion of the issue
- **WHEN** the review returns a `criterion_dropped` finding whose part is `issue` and whose section and quote are the text of an acceptance criterion of the issue
- **THEN** `open_findings` returns the finding

#### Scenario: The place in a comment line
- **WHEN** the comment lists a `spec_delta_wrong` finding on the requirement `A release keeps a Status` of `roadmap-item-claim`
- **THEN** its line starts with "- `spec_delta_wrong` at spec roadmap-item-claim (A release keeps a Status): "

### Requirement: A finding on a place that the plan does not hold is advice
A finding whose place the plan or the issue of the request does not hold SHALL be advice, whatever its type and its quote. A text of a tool answer SHALL NOT make a place that the plan holds. In a later review, the rule SHALL apply to each new finding on the revision, and an earlier finding that the review marks `holds` SHALL stay open with its place.

#### Scenario: A finding on a requirement that the plan does not hold
- **WHEN** the review of the plan of pull request #5350 at head ccfbab2e9586, whose spec delta changes three requirements of `roadmap-item-claim`, returns a `spec_delta_wrong` finding on a fourth requirement with a quote from a `read_spec` answer
- **THEN** `open_findings` returns no finding

#### Scenario: A finding on a requirement of the plan
- **WHEN** the review of the same plan returns a `spec_delta_wrong` finding on the requirement `A release keeps a Status that a job did not set` of `roadmap-item-claim` with a quote of the plan
- **THEN** `open_findings` returns the finding

#### Scenario: A group that the plan does not hold
- **WHEN** the review of a plan with two task groups returns a `missing_path` finding on group 3 with a quote of the plan
- **THEN** `open_findings` returns no finding

#### Scenario: A later review opens a finding on a requirement that the revision does not hold
- **WHEN** a later review marks the earlier finding `gone` and opens a `spec_delta_wrong` finding whose quote is in a block of `answer` and whose place is a requirement that the spec delta of the revision does not hold
- **THEN** the finding is advice, the planner gets no third request, and the staged change holds the revision with no open finding

#### Scenario: An earlier finding that holds keeps its place
- **WHEN** a later review marks `holds` an earlier finding on group 2, and the revision has one group
- **THEN** the finding stays open

### Requirement: The place check reads a name in another form
A key of the proposal or of the design SHALL be a place of both parts. The check SHALL compare the words of a name, so a heading sign, a title after a group number, a scenario name or a cut requirement name SHALL keep the place. The capability of a place SHALL be empty or a capability name, as a spec delta writes it.

#### Scenario: A finding that names the design for a key of the proposal
- **WHEN** the review of case 2166 of the golden set returns a `false_premise` finding on `design` (`feasibility`) that quotes the first line of `feasibility`
- **THEN** `open_findings` returns the finding

#### Scenario: A place in another form of its name
- **WHEN** the review of case 2166 returns findings with a quote of the plan on `task 2.1`, on `Requirement: F401 re-import ceiling check` of `ci-gate-admission`, on `## Feasibility` and on `Rejected alternatives`
- **THEN** `open_findings` returns each finding

#### Scenario: A capability with a space
- **WHEN** a finding names the capability `roadmap item claim`
- **THEN** the finding fails the schema
