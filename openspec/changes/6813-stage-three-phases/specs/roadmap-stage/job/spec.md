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
`--phase agent` SHALL refuse to start when its environment holds the App key or a GitHub token, and SHALL refuse an output folder that is there before its outputs.

#### Scenario: The App key
- **WHEN** the agent phase starts with `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY`, `GH_TOKEN` or `GITHUB_TOKEN` in its environment
- **THEN** it raises an error that names the variable, makes no model call and writes no output

#### Scenario: An output folder that is there
- **WHEN** `out/` is there before the agent phase starts
- **THEN** the phase raises `PhaseOutputError` and makes no model call

### Requirement: Publish of the stage Job reads its run files as data
`publish` SHALL read the state file and the outcome of the agent with `read_run_file`, with each text of the outcome masked. It SHALL refuse a link, a file that is not a regular file, a file over its limit, an outcome that is not of its model, a state file of another item and a change with a file outside its change folder, and SHALL push nothing then.

#### Scenario: A tampered output
- **WHEN** the outcome is a link, a FIFO or over 1 MiB, holds a key outside its model, or names a file outside the change folder, or the state file is a link
- **THEN** `publish` raises `PhaseOutputError`, pushes no branch and opens no pull request

#### Scenario: The end of the time budget in the agent phase
- **WHEN** the agent phase starts with no time left before the deadline of the Job
- **THEN** it plans nothing, and `publish` checks in with the result `deadline` and exits 143
