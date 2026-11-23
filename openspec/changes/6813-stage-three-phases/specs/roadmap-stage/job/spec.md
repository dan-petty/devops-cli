## ADDED Requirements

### Requirement: The stage Job takes a phase and a run folder
`devops roadmap stage --job-item <n> --confirm` SHALL take `--phase prepare|agent|publish|all` and `--work <folder>`, with `all` as the default, which runs the three phases in one process. A phase other than `all` SHALL need `--job-item`, `--confirm` and `--work`.

#### Scenario: A phase with no run folder
- **WHEN** `devops roadmap stage --job-item 1 --confirm --phase agent` runs with no `--work`
- **THEN** the command exits 1 and names `--work`

### Requirement: The stage Job runs its three phases on one run folder
`prepare` SHALL read the round of the item, make the writes that need no model, clone the staged commit into `work/`, and write the state file and the inputs of the agent. `agent` SHALL plan the item in that clone with no store and write its result to `out/`. `publish` SHALL write the result with `push_plan` and open or update the plan pull request.

#### Scenario: The phases in turn
- **WHEN** a test runs `prepare`, `agent` and `publish` in turn on one run folder, and `--phase all` on the same item with the same plan
- **THEN** both push the same tree to the branch of the item, open the same plan pull request, and write the same record and comments

#### Scenario: A prepare that ends the Job
- **WHEN** the round leaves the item out
- **THEN** `prepare` checks in and records the end, the agent phase plans nothing, and `publish` ends with the same end

#### Scenario: A failed GitHub read for the agent phase
- **WHEN** `prepare` reads the comments of the item for the agent phase, and GitHub answers HTTP 502
- **THEN** the item fails with the class `ci_infra` and the step `plan`, as a failed read in the plan does, and the Job exits 75

### Requirement: The agent phase of the stage Job holds no GitHub credential
`--phase agent` SHALL refuse to start when its environment holds the App key or a GitHub token, or when the token lookup of the session finds a gh login, and SHALL refuse an output folder that is there before its outputs.

#### Scenario: A gh login
- **WHEN** the agent phase starts with no token variable, and the token lookup of the session finds a gh login
- **THEN** it raises an error that names the login, makes no model call and writes no output

#### Scenario: The App key
- **WHEN** the agent phase starts with `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, `GH_TOKEN` or `GITHUB_TOKEN` in its environment
- **THEN** it raises an error that names the variable, makes no model call and writes no output

#### Scenario: An output folder that is there
- **WHEN** `out/` is there before the agent phase starts
- **THEN** the phase raises `PhaseOutputError` and makes no model call

### Requirement: Publish of the stage Job reads its run files as data
`publish` SHALL read the state file and the outcome of the agent with `read_run_file`, with each text of the outcome masked. It SHALL refuse a link, a file that is not a regular file, a file over its limit, an outcome that is not of its model and a state file of another item, and SHALL push nothing then.

#### Scenario: An output that is not data of its model
- **WHEN** the outcome is a link, a FIFO or over 1 MiB, nests too deep, or holds a key outside its model, or the state file is a link
- **THEN** `publish` raises `PhaseOutputError`, pushes no branch and opens no pull request

### Requirement: The agent phase hands over only what the model made
The agent phase SHALL hand over the proposal, the shorter text of the body, the review findings, the counts of the attempt and a trace that holds the tool, the argument and the outcome of each call and no answer and no match, or the stop, the cited paths of a return, the evidence of a false premise or the failure.

#### Scenario: A plan run with many full searches
- **WHEN** the trace of a plan holds 200 searches with full answers
- **THEN** the outcome holds at most 1 MiB, and `publish` opens the draft

### Requirement: Publish builds the result from the state of prepare
`publish` SHALL build the result from the state of `prepare` and what the model made, on the staged commit, with the steps that the planner runs after the model answers: the title, the body, the files rendered from the proposal, the secret check and the checks of the files. The blockers of a return SHALL come from the paths that the open plans create, as `prepare` read them, and each other text of the agent phase SHALL go through `safe_text`.

#### Scenario: The texts of the plan
- **WHEN** the agent phase hands over a plan with a shorter text, warnings, comment names and findings that hold a handle
- **THEN** the draft has the title and the body of `--phase all`, and each comment shows the handle in a code span

#### Scenario: A plan that a check refuses
- **WHEN** `openspec validate` refuses the change folder that `publish` renders, or the text of the proposal holds a closing keyword
- **THEN** `publish` raises `PhaseOutputError` and pushes nothing

#### Scenario: A return with no open plan
- **WHEN** the agent phase hands over a return for blockers whose paths no open plan creates
- **THEN** `publish` raises `PhaseOutputError` and returns no item

#### Scenario: The end of the time budget in the agent phase
- **WHEN** the agent phase starts with no time left before the deadline of the Job
- **THEN** it plans nothing, and `publish` checks in with the result `deadline` and exits 143
