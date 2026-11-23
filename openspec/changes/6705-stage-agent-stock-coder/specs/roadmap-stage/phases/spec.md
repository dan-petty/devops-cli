## Purpose

The phases `prepare`, `agent` and `publish` of the stage Job on one run folder. What each phase holds and decides, the stock `Coder` agent and its three checks, and the outputs that pass to `publish` as data. The checks of `publish` before its one push, and the default phase `all`, which runs the stage Job in one process.

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
`prepare` SHALL read the round of the item and make the writes of `StageWriter.begin`. It SHALL decide the job-time premise, the false premise of the body probe and the blocker of an open plan. When one of these ends the run, `prepare` SHALL write the end in `state/` and check in. A failed GitHub read SHALL fail the item with the class `ci_infra`.

#### Scenario: A failed read of the comments
- **WHEN** `prepare` reads the comments of the item and the store raises a GitHub error
- **THEN** the item records the class `ci_infra` and the step `plan`, and the command exits 75

#### Scenario: A blocker of an open plan
- **WHEN** the body of the item cites a path that the base lacks and the plan of an open item creates
- **THEN** `prepare` returns the item to New, the agent phase writes no output, and `publish` ends with the end of `prepare`

### Requirement: Prepare writes the run of the agent
When no decision ends the run, `prepare` SHALL clone the repository at the tip of the default branch. It SHALL commit the scaffold of the change folder with its date. It SHALL write the state file and an issue listing of at most 1 MiB in `state/`, and the inputs in `work/`. The listing SHALL be a list of `IssueRecord` with the number, the title, the URL and the state, and the body of the item only.

#### Scenario: A run that goes on
- **WHEN** `prepare` runs for a Ready item with two comments of a person and no false premise
- **THEN** the head of the clone holds the dated scaffold, and the inputs hold the body and the two comments whole

#### Scenario: A large repository
- **WHEN** the open issues of the store hold more than 1 MiB of text
- **THEN** the listing holds the body of the item only, and its size is below 1 MiB

### Requirement: The agent phase holds no GitHub credential
`--phase agent` SHALL refuse to start when its environment holds `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, `GH_TOKEN` or `GITHUB_TOKEN`, or when the token lookup of the session finds a gh login. It SHALL refuse an output folder that is there before its outputs.

#### Scenario: A token in the environment
- **WHEN** the agent phase starts with `GITHUB_TOKEN` in its environment
- **THEN** it raises an error that names the variable, makes no model call and writes no output

#### Scenario: An output folder that is there
- **WHEN** `out/` is there before the agent phase starts
- **THEN** the phase raises an error, makes no model call and writes no output

### Requirement: The stage agent is stock Coder with the three checks
The stage agent SHALL be one pydantic-ai `Agent` with `LocalWorkspace` at the clone, whose `env` holds a scratch `HOME` and `DEVOPS_CLI_CONFIG`. It SHALL hold `Coder` with `repo_context=False`, no `delegate_task` and its stock shell. `RequireVerification` SHALL have `exempt_paths=()` and patterns for the three checks in order. The run SHALL have no request limit.

#### Scenario: The capability list
- **WHEN** a test builds the stage agent with a clone and a stub model
- **THEN** the capabilities hold `LocalWorkspace`, `Coder` and `RequireVerification` with the three patterns in order, and each tool is a tool of the harness

#### Scenario: A recheck with no base
- **WHEN** the agent runs `devops roadmap plan-recheck --source . --branch HEAD` with no `--base`
- **THEN** `RequireVerification` records no check for the command

### Requirement: The agent phase hands over only what publish reads
The agent phase SHALL write the patch of the change folder from the base, the body candidate, and a `StageOutcome`. `StageOutcome` SHALL hold the end, the names of the failed checks as an enum, and fixed count fields, and no text of the model. The end SHALL be `unverified` after `CompletionUnverifiedEvent`, else `ended`, `timeout`, `provider`, `spend_limit` or `ci_infra`.

#### Scenario: A script that writes a plan file
- **WHEN** a stub agent writes a plan file with a script that no edit pattern matches, and ends
- **THEN** the outcome holds the end `ended`, and the patch holds the file

### Requirement: Publish trusts no end that the agent reports
`publish` SHALL decide the ends `ended` and `unverified` with its own checks. It SHALL accept `timeout` only after the end time in `state/`. It SHALL end a missing outcome, or an outcome outside its model, as `plan_defect`.

#### Scenario: An unverified end with good files
- **WHEN** the outcome holds `unverified`, and the files pass each check of `publish`
- **THEN** `publish` pushes the plan and opens the draft

#### Scenario: An early timeout
- **WHEN** the outcome holds `timeout` before the end time of the budget, and the files pass the checks
- **THEN** `publish` pushes the plan as for the end `ended`

#### Scenario: An outcome outside its model
- **WHEN** the outcome holds the end `premise_false` or a key outside its model
- **THEN** `publish` records `plan_defect`, exits 1 and returns no item to New

### Requirement: Publish counts only the ci_infra end of the agent toward the split limit
`publish` SHALL record an end `provider` or `spend_limit` of the agent with its class and its wait, and SHALL NOT count it toward `roadmap.stage.plan_defect_limit`. It SHALL count an end `ci_infra` of the agent toward that limit, and SHALL end as `plan_defect` the end that reaches it. `SPLIT_CLASSES` and `check_in` SHALL keep their behavior.

#### Scenario: A provider end
- **WHEN** the outcome holds the end `provider`
- **THEN** the item records `provider` with its wait, and its count of plan defects does not change

#### Scenario: Agent ci_infra ends up to the limit
- **WHEN** the outcome holds the end `ci_infra` on the third run on one body, with the limit 3
- **THEN** `publish` records `plan_defect`, and the item returns to New with the comment that asks for a split

### Requirement: Publish allows only the files of a plan
Before any check, `publish` SHALL allow only `.openspec.yaml`, `proposal.md`, `design.md`, `tasks.md` and `specs/**/spec.md` of the change folder. Each SHALL be UTF-8 text with the mode `100644`. Any other change, and a patch that `publish_patch` refuses, SHALL end as `plan_defect`, with no push.

#### Scenario: A path outside the change folder
- **WHEN** the patch of the agent changes `src/devops_cli/__init__.py` and the change folder
- **THEN** `publish` records `plan_defect`, exits 1 and pushes no branch

#### Scenario: A link
- **WHEN** the patch of the agent adds a link in the change folder
- **THEN** `publish` records `plan_defect`, not `ci_infra`, and pushes no branch

### Requirement: Publish checks the plan files in its one push
`publish` SHALL push once: the writer SHALL call `publish_patch`, with the checks in `before_push`. The checks SHALL refuse a secret and a `created` date that is not the date of `prepare`. They SHALL run `check_openspec`, `openspec validate --strict` and `recheck_plans` on the new tree, with the base, the default branch and the listing of `state/`.

#### Scenario: An ended outcome with a refused folder
- **WHEN** the outcome holds the end `ended` and the recheck refuses the change folder of the new tree
- **THEN** `publish` records `plan_defect`, exits 1 and pushes no branch

### Requirement: Publish classes the findings of its checks
`publish` SHALL end as `ci_infra` only a fixed list. The list holds the gate checks `version`, `configuration`, `skills` and `instructions`, a missing tool, and a network or GitHub error. A plan whose only finding is `group-over-budget` SHALL stop with `_stop_on_budget`, with no failure. Each other finding SHALL end as `plan_defect`.

#### Scenario: An OpenSpec off its pin
- **WHEN** the `openspec` on PATH has another version than `package-lock.json` pins, and the plan files pass each other rule
- **THEN** `publish` records `ci_infra`, pushes no branch and exits 75

#### Scenario: An overlap of two changes
- **WHEN** the plan modifies a requirement that another active change modifies
- **THEN** `publish` records `plan_defect`, exits 1 and pushes no branch

#### Scenario: A group over the budget
- **WHEN** the only finding of the checks is `group-over-budget`
- **THEN** `publish` posts the owner question of `_stop_on_budget`, records no failure and pushes no branch

### Requirement: Publish builds the texts of the plan with the stage functions
`publish` SHALL build the title and the body with the stage builder that `plan-recheck --candidate` uses. The title SHALL come from the summary of the candidate, else from the issue title. The body SHALL come from the candidate, else from the Why of the proposal, else from the issue title. A closing keyword SHALL end the item as `plan_defect`.

#### Scenario: A body text that the form refuses
- **WHEN** the text of the candidate is longer than the room of the plan body
- **THEN** the body holds the Why section of the proposal, and the item gets no failure

### Requirement: Publish cleans each text before the writer of phase all
Each text of `publish` SHALL go through `safe_text` once. Before it calls the writer, `publish` SHALL remove each control character other than the line feed from each text that it hands over. It SHALL fit the plan-state comment to 65536 characters. The writer SHALL keep its behavior for `--phase all`.

#### Scenario: A handle and a control character
- **WHEN** the text of the candidate holds `@octocat`, `<b>` and the character U+001B
- **THEN** the body holds `@octocat` in one code span, `&lt;b>` once, and no U+001B

#### Scenario: Long group titles
- **WHEN** the group titles of the plan give a plan-state comment of more than 65536 characters
- **THEN** the posted comment holds at most 65536 characters, the plan files keep the full titles, and the item gets no failure

### Requirement: Publish writes from a clone of its own
`publish` SHALL clone the repository at the base of `prepare` into a folder of its own home, and SHALL give that clone to the writer. It SHALL run no git command in a folder under `work/`.

#### Scenario: The git commands of publish
- **WHEN** a test records the folder of each git command of a `publish` that stages a plan
- **THEN** no folder of a command is under `work/`

### Requirement: The same plan gives the same publish in both forms
For one plan and one commit time, the separate phases SHALL push the same commit as `--phase all`. They SHALL write the same title, body, labels, record and comments.

#### Scenario: One plan in both forms
- **WHEN** a stub agent writes the files and the candidate that `--phase all` renders for one stub plan, with a fixed commit time
- **THEN** both forms push the same commit, open a draft with the same title, body and labels, and write the same record and comments

### Requirement: The separate phases share one time budget and one request budget
`prepare` SHALL write the GitHub requests that it sent and the end time of the time budget. That end time SHALL be at most the deadline of the Job less `CONST_ROADMAP_STAGE_JOB_MARGIN_SECONDS`. The agent phase SHALL stop before a model request after that end time. `publish` SHALL count the requests of `prepare` in its budget. A SIGTERM in the agent phase SHALL write no check-in.

#### Scenario: An agent phase past its time budget
- **WHEN** the agent phase starts after the end time of the budget
- **THEN** it makes no model call and writes the end `timeout`, and `publish` checks in with the result `deadline` and exits 143

#### Scenario: A SIGTERM in the agent phase
- **WHEN** the agent phase gets a SIGTERM during the run
- **THEN** it exits with the status of its class and writes no check-in on the item
