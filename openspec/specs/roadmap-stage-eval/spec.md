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
`devops roadmap eval stage` SHALL plan each case with the stage planner, the model of the `stage` task or `--model`, and a checkout of the commit of the case. It SHALL judge the first reply with the gates, and print for each scored defect type the cases that have it, how many the model avoided, how many a gate caught, and the rate, with a total. It SHALL show no rate for a type that no gate judges, nor for the gate `kind`. It SHALL store the report as JSON under the data directory.

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
`devops roadmap eval verify` SHALL run the verification pass on the plan of each case of the golden set as an agent with the read-only tools of the stage job, on the checkout of the commit of the case, with the model of the `verification` task or `--model`. It SHALL print the recall of the labeled defects (all, and the blocker and major ones), the recall for each type, and the count of findings on the `good` plans, and SHALL store the score as JSON under `.data/`.

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
The command SHALL end a case whose model call fails as `failed`, count it as no defect found, run the other cases, and exit 1. `--dry-run` SHALL make no request to a model or to git and SHALL list the cases and the one agent run for each. The command SHALL carry the dry-run class `request-plan`.

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

### Requirement: The golden set holds a case of the open-finding stop
The golden set SHALL hold a case recorded from #3174 whose plan carries a single group titled `placeholder`, and the replay SHALL report that case with its defect.

#### Scenario: The replay runs the recorded case
- **WHEN** The replay runs the case recorded from #3174.
- **THEN** The report lists the case with its placeholder group, and the test asserts the expected result.

### Requirement: The replay reads the search evidence from its case
The stage eval replay MUST read the negative-search evidence from the `search_evidence` mapping of its case and MUST run no git command.

#### Scenario: The replay judges a negative search
- **WHEN** The stage eval replay judges a plan with a negative-search verify command.
- **THEN** The replay reads the evidence from the case and runs no git grep.

### Requirement: The golden set holds the case of a refused and a kept negative search
The stage eval case MUST hold the move plan of the stage modules with its recorded search evidence and MUST assert the no-hit refusal, the refusal of the bare prefix `devops_cli.roadmap.stage.stage`, and the acceptance of the dotted prefix `devops_cli.roadmap.stage_`.

#### Scenario: The replay runs the case of the moved modules
- **WHEN** The stage eval replay runs the case of the move of the stage modules.
- **THEN** The replay reports the two refusals and the acceptance for the dotted prefix `devops_cli.roadmap.stage_`.

### Requirement: The live report states the tokens and the spend of the run
The JSON report and the printed score of a live run SHALL state the input tokens and the output tokens of the model calls of the run, and the spend in USD at the hosted price of the model. The spend SHALL be null in the report, and the printed score SHALL say that no price is known, when the price registry holds no price for the model.

#### Scenario: A priced model
- **WHEN** a live run of `claude-sonnet-5-5` ends
- **THEN** the report holds `usage` with the input tokens, the output tokens and a spend equal to the hosted price of those tokens, and the printed score has the line `Tokens: <in> in, <out> out.`

#### Scenario: A model with no price
- **WHEN** a live run of a model that has no price ends
- **THEN** the `spend_usd` of the report is null and the printed score says `Spend: no price for the model.`

### Requirement: The workflow document defines an acceptable stage score and the baseline
`docs/ROADMAP_WORKFLOW.md` SHALL define an acceptable stage score with a recall threshold of the blocker and major defects, a rule of no finding on the good plans and a share of live plans, and SHALL record the commands of the baseline run, the setting `ai.tasks.stage.model` and the work that waits for the baseline.

#### Scenario: The workflow document states the threshold
- **WHEN** a test reads the stage measurement section of `docs/ROADMAP_WORKFLOW.md`
- **THEN** it holds the recall threshold, the rule for the good plans of the golden set and the share of live plans

#### Scenario: The workflow document names the baseline procedure
- **WHEN** a test reads the stage measurement section
- **THEN** it names `eval stage` with `--no-toolbox`, `eval verify`, `ai.tasks.stage.model` and the parked items #3066 and #3060

### Requirement: The verify run is the pass of the stage job
The run SHALL give the agent the OpenSpec tool that the stage job gives `read_spec` and the context window of the task `verification`, and `--model` SHALL keep the other settings of that task.

#### Scenario: A run reads a spec
- **WHEN** the verifier calls `read_spec` in a run
- **THEN** the tool answers from the specs of the checkout of the case

#### Scenario: The model option keeps the task
- **WHEN** the command runs with `--model` and the task `verification` sets a provider
- **THEN** the review runs on that provider with the model of the option

### Requirement: The verify report states the recall floor
The report SHALL state the recall floor `CONST_ROADMAP_VERIFY_RECALL_FLOOR` and whether the recall of the blocker and major defects meets it.

#### Scenario: The report states the floor
- **WHEN** the command runs on the set
- **THEN** the report states the floor of 90 percent of the blocker and major defects and whether the recall of those defects reaches it

### Requirement: The golden set holds a test-only group that delivers its criterion and the same plan without the code
The golden set SHALL hold the merged plan of #3410 as a `good` case, and a reviewed case whose plan is the same plan without the group that adds the field of the case model. The reviewed case SHALL hold one `criterion_dropped` defect with the gate `none` and a `reason`. In both plans the group that adds the case of a move of the stage modules SHALL change only test files and fixture files.

#### Scenario: The replay lists the dropped criterion
- **WHEN** The stage eval replay runs the reviewed case of #3410.
- **THEN** The report lists one `criterion_dropped` defect with the gate `none`, and no gate refuses the plan.

#### Scenario: The good twin passes every gate
- **WHEN** The stage eval replay runs the good case of #3410.
- **THEN** Every gate accepts the plan, and the case is the twin of the reviewed case.

#### Scenario: The two plans differ by one group
- **WHEN** The groups of the two plans are compared.
- **THEN** The reviewed plan holds the groups of the good plan except the group that changes `src/devops_cli/roadmap/stage/stage_eval_cases.py`.

### Requirement: A case that holds no commit is left out and named
A case with the commit `NO_COMMIT`, forty zeros, as its `base_commit` holds no commit, as the change of its plan was never merged as that plan. `devops roadmap eval verify` and `devops roadmap eval stage` SHALL leave such a case out of a live run and of a dry run, by one shared rule that reads no git. The text report and the JSON report (`left_out`) SHALL name each left-out case. A left-out case SHALL NOT count in the cases, in the labeled defects, in the score or in the exit code.

#### Scenario: The verify command leaves a case out
- **WHEN** `devops roadmap eval verify` runs on a set of one case with a commit and one case with `NO_COMMIT`, and the model finds the defect of the first case
- **THEN** the command exits 0, the model gets one call, the report counts one case and the defects of that case only, and the text and the JSON name the left-out case

#### Scenario: The stage command leaves a case out
- **WHEN** `devops roadmap eval stage` runs on the same set
- **THEN** the command exits 0, the score counts one case, and the text and the JSON name the left-out case

#### Scenario: The dry run leaves a case out
- **WHEN** either command runs with `--dry-run` on a set that holds a case with `NO_COMMIT`
- **THEN** the output lists the model calls of the other cases only, names the left-out case, and makes no request

### Requirement: A run with no case to check out fails, and the replay keeps every case
When the selection holds no case with a commit, the command SHALL exit 1 and name the cases. `devops roadmap eval stage --replay` reads no git and SHALL keep every case.

#### Scenario: Nothing is left to run
- **WHEN** `--case` picks only a case with `NO_COMMIT`
- **THEN** the command exits 1 and names the case

#### Scenario: The replay keeps the case
- **WHEN** `devops roadmap eval stage --replay` runs with `--case` for a case with `NO_COMMIT`
- **THEN** the replay runs the case and exits 0

### Requirement: A commit that git cannot check out ends its case and not the run
When git cannot check out the `base_commit` of a case in the live run of `devops roadmap eval stage`, the case SHALL end `failed` with the git error as its reason. The other cases SHALL run, the report SHALL be stored, and the command SHALL exit 1.

#### Scenario: A repository without the commit
- **WHEN** a live run has two cases, and the repository lacks the commit of the first
- **THEN** the first case ends `failed`, the second case is staged, the report is stored with both outcomes, and the command exits 1

### Requirement: Each commit of the set is a real commit or the case reads none
The `base_commit` and the `merge_commit` of each case of the golden set SHALL each be the full hash of a commit of this repository, or `NO_COMMIT` in a case whose notes say that it reads no commit.

#### Scenario: The commits of the set
- **WHEN** the test reads the 45 cases
- **THEN** each hash that is not `NO_COMMIT` has 40 hexadecimal characters and names a commit of this repository, and each case with `NO_COMMIT` has a note that says it reads no commit

### Requirement: The golden set holds the incident plan
The golden set SHALL hold the plan of pull request #3305 as a case whose `issue` is 3264.

#### Scenario: The incident case loads
- **WHEN** `load_cases` reads `tests/fixtures/roadmap_eval/stage` at the commit that holds the case
- **THEN** the cases hold a case whose `issue` is 3264 and whose `pull` is 3305

#### Scenario: The note names the claim
- **WHEN** the case of pull request #3305 is read
- **THEN** one note of the case holds the text `kind: placeholder`

#### Scenario: The incident case passes every gate
- **WHEN** `replay_all` runs on the case of pull request #3305
- **THEN** `report.failures` is an empty list

### Requirement: The replay reports a plan that leaves out the prompt reply key
The golden set SHALL hold a case whose plan adds a field to `StageProposal` and changes no reply key of the prompt, and the replay SHALL report that defect as caught by the `prompt_keys` gate.

#### Scenario: Recorded missing prompt key
- **WHEN** The replay runs the gates on a case with a `prompt_key_missing` defect whose gate is `prompt_keys`.
- **THEN** The replay reports the defect as caught, and a gate stops it when the gate no longer refuses the plan.

#### Scenario: A plan that names the reply key
- **WHEN** The replay runs the gates on a `good` case whose plan adds a field to `StageProposal` and changes the prompt with the reply key.
- **THEN** The `prompt_keys` gate finds no problem, and the replay reports no failure.

### Requirement: The replay of the golden set runs once per test module
The eval gate test module SHALL compute the replay of the golden set once in a module-scoped fixture, and SHALL give each case of the set its own parametrized test item.

#### Scenario: One item for each case
- **WHEN** A test reads the parametrize mark of the case test in the eval gate test module
- **THEN** The mark's values are the list that load_cases returns, so pytest collects one item for each case.

#### Scenario: The report tests share one replay
- **WHEN** A test reads the source of the eval gate test module
- **THEN** The whole-set replay_all call sits in the module-scoped fixture, and no report test calls replay_all itself.

### Requirement: The golden set holds a plan whose read claim its trace does not support
The golden set SHALL hold a replay case from #3205 or #3237 whose facts give a trace of zero calls, and the replay SHALL refuse its unsupported read claim.

#### Scenario: The replay refuses the case
- **WHEN** `devops roadmap eval stage --replay` runs on the golden set.
- **THEN** The case is present, and the `paths` gate refuses its unsupported read claim.

### Requirement: The golden set records the reference hits of a case
The `facts.json` of a stage case SHALL hold a `references` list: the paths of the files that hold the old path or the dotted name of a moved module. A case with no `references` key SHALL read an empty list, so its verdict stays as it is. `PlanUnderTest` SHALL hold the recorded paths, and the `paths` gate SHALL pass them to `check_proposal` as its reference hits.

#### Scenario: Recorded hits reach the plan
- **WHEN** the replay loads a case whose `facts.json` holds two reference paths
- **THEN** `PlanUnderTest.of_case` holds the same two paths in its `references` field

#### Scenario: The check receives the hits
- **WHEN** the replay runs the `paths` gate on a case with two recorded reference paths
- **THEN** `check_proposal` receives the same two paths as its reference hits

#### Scenario: An existing case replays as before
- **WHEN** the replay runs the whole golden set with a case that has no `references` key
- **THEN** that case reads an empty list and the report lists no failure for it

### Requirement: The golden set holds a missed reference hit
The golden set SHALL hold a case that moves a module and leaves a string literal of the old name in `tests/`, with one `missing_path` defect that names the test file and the gate `paths`.

#### Scenario: The replay catches the missed reference
- **WHEN** the replay runs the new case
- **THEN** the `paths` gate refuses the plan and the report marks the defect `caught`

### Requirement: The live run reads the runner facts in the checkout
The live run SHALL build the facts context of a case with the same builder as the stage job. It SHALL read each source file of that context at the commit of the case, and when the commit lacks the file, in the checkout of the run. The stage job SHALL read the staged commit only. A file that neither the commit nor the checkout holds SHALL end the case `refused` with the path.

#### Scenario: A commit that lacks the fact files
- **WHEN** a case commit holds no `src/devops_cli/roadmap/failure.py` and no `src/devops_cli/roadmap/runner_tools.py`, the checkout holds both, and the issue text cites a failure word and a tool
- **THEN** the case reaches the model and does not end `refused`

#### Scenario: A file that the checkout lacks too
- **WHEN** neither the commit nor the checkout holds `src/devops_cli/roadmap/runner_tools.py`
- **THEN** the case ends `refused` and the reason names `src/devops_cli/roadmap/runner_tools.py`

#### Scenario: The job keeps its error
- **WHEN** the stage job plans an item and the staged commit lacks `src/devops_cli/roadmap/failure.py`
- **THEN** the job raises `RoadmapStageError` and makes no model call

### Requirement: The live report counts the degenerate cases
The live run SHALL end a case with the outcome `degenerate` when the stage planner stops it on a reply that is a placeholder in every text, and the report SHALL show the count of such cases in the line of how the cases ended, `0` when there are none.

#### Scenario: A reply of placeholders
- **WHEN** the model answers a case with `x` or `placeholder` in every text of the plan
- **THEN** the case ends `degenerate` after one model call, and the report shows `degenerate 1`

#### Scenario: A run with no such reply
- **WHEN** the live run finishes and no reply is a placeholder in every text
- **THEN** the report shows `degenerate 0`

### Requirement: A labelled set holds the cases of the Jev completeness check
The folder `tests/fixtures/roadmap_eval/completeness/` SHALL hold at least 30 cases with at least 10 of each label, `complete` and `incomplete`. A case SHALL hold `case.json` (label, kind, criteria, source) and `draft.diff`. An incomplete case SHALL be a plan with a dropped criterion, or a complete diff from which one hunk is removed and named in `removed`.

#### Scenario: The set loads
- **WHEN** the committed set is loaded
- **THEN** it holds at least 30 cases with at least 10 of each label, and the diff of each case fits `CONST_ROADMAP_JEV_MAX_DIFF_TOKENS`

#### Scenario: A removed-hunk case
- **WHEN** a case names a removed hunk
- **THEN** the diff of its complete twin holds the hunk and the diff of the case does not

### Requirement: The command scores the check and decides on the switch
`devops roadmap eval completeness` SHALL send one request to Jev for each case and print the recall of the incomplete drafts, the false holds, and the spend. It SHALL store a JSON report with the probability of each criterion. It SHALL say that the switch stays off when the false holds exceed `CONST_ROADMAP_JEV_EVAL_MAX_FALSE_HOLD_RATE` or the set is too small. With `--dry-run` it SHALL send no request.

#### Scenario: A run
- **WHEN** the command runs on a set with Jev answering
- **THEN** it sends one request for each case, prints the recall and the false holds, and stores the report

#### Scenario: A dry run
- **WHEN** the command runs with `--dry-run`
- **THEN** it lists the requests and sends none
