## Purpose

The phases `prepare`, `agent` and `publish` of the stage Job on one run folder: what each phase holds and decides, the stock `Coder` agent and its three checks, the outputs that pass from the agent to `publish` as data, the checks of `publish` before any push, and the default phase `all`, which runs the stage Job in one process.

## ADDED Requirements

### Requirement: The stage Job takes a phase and a run folder
`devops roadmap stage --job-item <n> --confirm` SHALL take `--phase prepare|agent|publish|all` and `--work <folder>`, with `all` as the default. A phase other than `all` SHALL need `--job-item`, `--confirm` and `--work`. The command SHALL refuse `--source` with `--phase agent` and with `--phase publish`.

#### Scenario: A phase with no run folder
- **WHEN** `devops roadmap stage --job-item 1 --confirm --phase agent` runs with no `--work`
- **THEN** the command exits 1, names `--work` and runs no phase

#### Scenario: A source for publish
- **WHEN** `devops roadmap stage --job-item 1 --confirm --phase publish --work <folder> --source <clone>` runs
- **THEN** the command exits 1, names `--source` and runs no phase

### Requirement: The default phase runs the stage Job in one process
`devops roadmap stage --job-item <n> --confirm` with no `--phase` SHALL run `run_stage_job` in one process and SHALL write no state file and no outcome file.

#### Scenario: No phase
- **WHEN** a test runs `devops roadmap stage --job-item 1 --confirm` with no `--phase` and a stub model
- **THEN** the command calls `run_stage_job`, builds no stage agent, and the data folder holds no `state.json` and no `outcome.json`

### Requirement: Prepare decides what needs no model
`prepare` SHALL read the round of the item, make the writes of `StageWriter.begin`, and decide the job-time premise, the false premise of the body probe and the blocker of an open plan. When one of these ends the run, `prepare` SHALL write the end in `state/` and check in. A failed GitHub read SHALL fail the item with the class `ci_infra`.

#### Scenario: A failed read of the comments
- **WHEN** `prepare` reads the comments of the item and the store raises a GitHub error
- **THEN** the item records the class `ci_infra` and the step `plan`, and the command exits 75

#### Scenario: A blocker of an open plan
- **WHEN** the body of the item cites a path that the staged commit lacks and the plan of an open item creates
- **THEN** `prepare` returns the item to New with the blocker, writes `ended` in `state/`, the agent phase writes no output, and `publish` ends with the end of `prepare`

### Requirement: Prepare writes the run of the agent
When no decision ends the run, `prepare` SHALL clone the repository at the tip of the default branch into `work/`, write the scaffold of the change folder with the date of `prepare`, and write `state/state.json`, `state/issues.json`, `work/input.json` and `work/issues.json`. The inputs SHALL hold the whole body of the item and each comment of a person with write access or of the App.

#### Scenario: A run that goes on
- **WHEN** `prepare` runs for a Ready item with two comments of a person and no false premise
- **THEN** the clone holds the scaffold of the change folder with the date that the state holds, and the inputs of the agent hold the body and the two comments whole

### Requirement: The agent phase holds no GitHub credential
`--phase agent` SHALL refuse to start when its environment holds `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, `GH_TOKEN` or `GITHUB_TOKEN`, or when the token lookup of the session finds a gh login. It SHALL refuse an output folder that is there before its outputs.

#### Scenario: A token in the environment
- **WHEN** the agent phase starts with `GITHUB_TOKEN` in its environment
- **THEN** it raises an error that names the variable, makes no model call and writes no output

#### Scenario: A gh login
- **WHEN** the agent phase starts with no token variable, and the token lookup of the session finds a gh login
- **THEN** it raises an error that names the login, makes no model call and writes no output

### Requirement: The stage agent is stock Coder with the three checks
The stage agent SHALL be one pydantic-ai `Agent` with `LocalWorkspace` at the clone of `prepare`, `Coder` with no `delegate_task`, and `RequireVerification` whose `verification_commands` match `devops openspec check`, `openspec validate <change> --strict` and `devops roadmap plan-recheck --source . --branch HEAD`, in this order, with `exempt_paths=()`. The agent SHALL have no tool of `stage_tools` or `stage_toolbox`, and its run SHALL have no request limit.

#### Scenario: The capability list
- **WHEN** a test builds the stage agent with a clone and a stub model
- **THEN** the capabilities hold `LocalWorkspace` at the clone, `Coder`, and `RequireVerification` with the three patterns in order and an empty `exempt_paths`, and each tool name is a tool of the harness

#### Scenario: A probe of a check
- **WHEN** the agent runs `devops openspec check --help` or `devops roadmap plan-recheck --source .` with no `--branch`
- **THEN** `RequireVerification` records no check for the command

### Requirement: The agent phase hands over only what publish reads
The agent phase SHALL write `out/plan.patch` with the change folder only, from the base of `prepare`, `out/candidate.md`, and `out/outcome.json`. The outcome SHALL hold the end, one failure class of `plan_defect`, `timeout`, `provider`, `spend_limit` and `ci_infra`, the names of the failed checks as an enum, and counts. It SHALL hold no text of the model.

#### Scenario: A plan run
- **WHEN** a stub agent writes the change folder and the candidate, commits them and runs the three checks with a pass
- **THEN** the patch changes only paths under `openspec/changes/<change>/`, and the outcome holds the end `verified`, no failure class and the counts of the run

### Requirement: An unverified run ends as plan_defect
A run of the stage agent that emits `CompletionUnverifiedEvent` SHALL write the end `unverified` with the names of its failed checks. `publish` SHALL check in with the failure class `plan_defect`, exit 1 and push no branch.

#### Scenario: A run that ends unverified
- **WHEN** a test runs the agent phase with a stub model that edits a plan file and ends with the last `devops openspec check` failed, then runs `publish`
- **THEN** the record of the item holds `plan_defect` and its count on the body, the command exits 1, and the branch of the item does not exist

### Requirement: Publish checks the plan files again before any push
`publish` SHALL read `state/` and `out/` with `read_run_file`. Before any push it SHALL refuse a path outside `openspec/changes/<change>/`, a secret, a `created` date that is not the date of `prepare`, and a tree that `devops openspec check`, `openspec validate --strict` or `plan-recheck` with the issue listing of `state/` refuses. It SHALL end each refused output, each refused path and each failed check as `plan_defect`, with exit 1, no push and no `ci_infra` retry.

#### Scenario: A path outside the change folder
- **WHEN** the patch of the agent changes `src/devops_cli/__init__.py` and the change folder
- **THEN** `publish` records `plan_defect`, exits 1 and pushes no branch

#### Scenario: A verified outcome with a refused folder
- **WHEN** the outcome holds the end `verified` and `plan-recheck` refuses the change folder of the new tree
- **THEN** `publish` records `plan_defect`, exits 1 and pushes no branch

#### Scenario: An outcome outside its model
- **WHEN** `out/outcome.json` holds the failure class `premise_false` or a key outside its model
- **THEN** `publish` records `plan_defect`, exits 1 and returns no item to New

### Requirement: Publish builds the texts of the plan with the stage functions
`publish` SHALL build the title with `staging_title` from the summary of the candidate, else from the summary of the issue title, and the body with `pull_request_body` from the text of the candidate, else from the Why of `proposal.md`, else from the issue title. A closing keyword in the summary or the text SHALL end the item as `plan_defect`. The commit message SHALL be the title and `Plans #<n>.`, and the labels SHALL come from the title, as for `--phase all`.

#### Scenario: A candidate with a closing keyword
- **WHEN** the text of the candidate holds a closing keyword before a reference to another issue
- **THEN** `publish` records `plan_defect`, exits 1 and pushes no branch

#### Scenario: A body text that the form refuses
- **WHEN** the text of the candidate is longer than the room of the plan body
- **THEN** the body holds the Why section of the proposal, and the item gets no failure

### Requirement: Each comment text is clean and fits GitHub
Each text of `publish` SHALL go through `safe_text` once. The stage writer SHALL remove each control character other than the line feed from the body and from each comment that it posts, and each comment SHALL hold at most 65536 characters.

#### Scenario: A handle and a control character
- **WHEN** the text of the candidate holds `@octocat`, `<b>` and the character U+001B
- **THEN** the body holds `@octocat` in one code span, `&lt;b>` once, and no U+001B

#### Scenario: A long plan-state comment
- **WHEN** the groups of the plan give a plan-state comment of more than 65536 characters
- **THEN** the posted comment holds at most 65536 characters and the item gets no failure

### Requirement: The same plan gives the same publish in both forms
For one plan, the separate phases SHALL push the same tree and write the same title, body, labels, record and comments as `--phase all`.

#### Scenario: One plan in both forms
- **WHEN** a stub agent writes the files that `--phase all` renders for one stub plan, with the summary and the text of that plan as the candidate
- **THEN** both forms push the same tree to the branch of the item, open a draft with the same title, body and labels, and write the same record and comments

### Requirement: The separate phases share one time budget and one request budget
`prepare` SHALL write the end time of the time budget of the Job, cut to the deadline of the Job less `CONST_ROADMAP_STAGE_JOB_MARGIN_SECONDS`, and the GitHub requests that it sent. The agent phase SHALL stop before a model request after that end time, and `publish` SHALL count the requests of `prepare` in its request budget. A SIGTERM in the agent phase SHALL write no check-in.

#### Scenario: An agent phase past its time budget
- **WHEN** the agent phase starts after the end time of the budget
- **THEN** it makes no model call and writes the end `timeout`, and `publish` checks in with the result `deadline` and exits 143
