## ADDED Requirements

### Requirement: The stage context lists an overlapping pull request
The stage context builder SHALL list each open pull request that changes a path that the item body cites, with its number, title, state and the shared paths.

#### Scenario: A fake pull request changes a cited path
- **WHEN** A test gives the builder a fake client that holds pull request 3173, which changes `docs/TELEMETRY.md`, and an item body that cites `docs/TELEMETRY.md`.
- **THEN** The context holds one entry with number 3173, its title, its state and `docs/TELEMETRY.md`.

#### Scenario: A fake pull request changes a path that no item body cites
- **WHEN** A test gives the builder a fake client that holds pull request 3173, which changes `docs/TELEMETRY.md`, and an item body that cites only `src/devops_cli/roadmap/stage.py`.
- **THEN** The context holds no overlap entry.

### Requirement: A plan pull request carries a plan mark
The stage context builder SHALL mark an open pull request whose title has the type `docs(openspec)` as a plan pull request.

#### Scenario: A plan pull request overlaps a cited path
- **WHEN** A test gives the builder a fake client that holds pull request 3252, titled `docs(openspec): plan #3252 stage context`, which changes `src/devops_cli/roadmap/stage_overlap.py`, and an item body that cites that path.
- **THEN** The context entry holds the number, the title, the state, the plan mark and `src/devops_cli/roadmap/stage_overlap.py`.

#### Scenario: A pull request that is no plan carries no mark
- **WHEN** A test gives the builder a fake client that holds pull request 3253, titled `feat(roadmap): stage context`, which changes `src/devops_cli/roadmap/stage.py`, and an item body that cites that path.
- **THEN** The context entry holds the number and no plan mark.

### Requirement: A cited metric lists its other senders
For each cited metric name, the stage context builder SHALL list the other files that hold the name, from `git grep -w` at the staged commit.

#### Scenario: A cited counter lists the files that hold its name
- **WHEN** A test gives the builder an item body that cites `devops_cli_github_requests_total` and a staged tree that holds the name in two files.
- **THEN** The context lists `src/devops_cli/telemetry/instruments.py` and `docs/TELEMETRY.md` under the cited name.

#### Scenario: A name that `INSTRUMENTS` does not hold lists no sender
- **WHEN** A test gives the builder an item body that cites `devops_cli_dashboard_panel` and a staged tree that holds the name in one file.
- **THEN** The context lists no sender under that name.

### Requirement: The gate refuses an empty Dependencies part on an overlap
`check_proposal` SHALL refuse a reply whose `dependencies` field is empty when the context lists an overlap, and SHALL name the pull request and the shared path.

#### Scenario: An overlap with an empty Dependencies field
- **WHEN** `check_proposal` gets a reply whose `dependencies` field is empty and a context that lists pull request 3173 on `docs/TELEMETRY.md`.
- **THEN** The problems hold one sentence that names pull request 3173 and `docs/TELEMETRY.md`.

#### Scenario: A reply that names the overlap passes
- **WHEN** `check_proposal` gets a reply whose `dependencies` field names pull request 3173 and `docs/TELEMETRY.md`, and a context that lists that overlap.
- **THEN** The problems hold no sentence about the overlap.

### Requirement: The stage prompt states the Dependencies rule
The stage prompt SHALL tell the planner to write each overlap and each shared metric sender into the `dependencies` field.

#### Scenario: The prompt holds the Dependencies rule
- **WHEN** A test reads the stage prompt file.
- **THEN** The prompt holds a rule that names the `dependencies` field, the empty list and the overlap entry.

### Requirement: The overlap read costs a stated number of GitHub requests
The stage context builder SHALL read the open pull requests and their files in one GraphQL request for each 100 open pull requests, and SHALL state that count in the comment of the staged item.

#### Scenario: 150 open pull requests cost two requests
- **WHEN** A test gives the builder a fake client and 150 open pull requests.
- **THEN** The fake client records two GraphQL requests and no other request.
