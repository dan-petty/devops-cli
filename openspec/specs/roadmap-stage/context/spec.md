# roadmap-stage/context Specification

## Purpose
What the stage context gives the planner beside the issue: the open pull requests that overlap the plan, the Dependencies rule, the other senders of a metric, the failure taxonomy, and the facts of the runner and the repository.

## Requirements

### Requirement: The stage context lists an overlapping pull request
The stage context builder SHALL list each open pull request that changes a path that the item body cites, with its number, title, state and the shared paths.

#### Scenario: A fake pull request changes a cited path
- **WHEN** A test gives the builder a fake client that holds pull request 3173, which changes `docs/TELEMETRY.md`, and an item body that cites `docs/TELEMETRY.md`.
- **THEN** The context holds one entry with number 3173, its title, its state and `docs/TELEMETRY.md`.

#### Scenario: A fake pull request changes a path that no item body cites
- **WHEN** A test gives the builder a fake client that holds pull request 3173, which changes `docs/TELEMETRY.md`, and an item body that cites only `src/devops_cli/roadmap/stage/stage.py`.
- **THEN** The context holds no overlap entry.

### Requirement: A plan pull request carries a plan mark
The stage context builder SHALL mark an open pull request whose title has the type `docs(openspec)` as a plan pull request.

#### Scenario: A plan pull request overlaps a cited path
- **WHEN** A test gives the builder a fake client that holds pull request 3252, titled `docs(openspec): plan #3252 stage context`, which changes `src/devops_cli/roadmap/stage/stage_overlap.py`, and an item body that cites that path.
- **THEN** The context entry holds the number, the title, the state, the plan mark and `src/devops_cli/roadmap/stage/stage_overlap.py`.

#### Scenario: A pull request that is no plan carries no mark
- **WHEN** A test gives the builder a fake client that holds pull request 3253, titled `feat(roadmap): stage context`, which changes `src/devops_cli/roadmap/stage/stage.py`, and an item body that cites that path.
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

### Requirement: A closed plan is no dependency
The stage job SHALL ignore the plan of a closed item when it finds a dependency or an overlapping create path. The stage job SHALL ignore the plan of an archived change in the same way.

#### Scenario: A closed item's plan names the same path
- **WHEN** a closed item's active change folder on the default branch lists the cited path as `(new)`
- **THEN** the stage job records no dependency on that item, and the check accepts a reply that lists the path in `creates`

#### Scenario: An archived change names the path
- **WHEN** the change folder of an open item is archived on the default branch, and it lists the cited path as `(new)`
- **THEN** the stage job records no dependency on that item, and the check accepts a reply that lists the path in `creates`

### Requirement: The planner prompt names the issue form of a dependency
The planner prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL state that a `dependencies` entry which starts with `#<number>:` names an issue that must be delivered first, and MUST keep the rule that names each overlap and each metric sender.

#### Scenario: The prompt-rules test reads the form
- **WHEN** the prompt-rules test reads the dependencies rule of `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the test finds the form `#<number>:` and the rule of the overlaps, and it passes

### Requirement: Failure taxonomy in staging context
Staging context SHALL include the failure class table and action rules of the installed `devops_cli.roadmap.failure` module when the plan cites retry, review, stop, tier or failure. A staged commit that holds no devops-cli file gets them too.

#### Scenario: Retry plan gets class table
- **WHEN** A staging run gets a plan that cites `retry`, and the staged commit holds no `src/devops_cli/roadmap/failure.py`.
- **THEN** The planner context contains the class table and the `ACTION_BY_CLASS` rules of the installed module, and the run raises no `RoadmapStageError`.

### Requirement: Runner capability facts in staging context
Staging context SHALL include the runner tools and the `NOT_IN_RUNNER` entries of the installed `devops_cli.roadmap.runner_tools` module, each entry with its reason text, when the plan cites a command or tool name. A staged commit that holds no devops-cli file gets them too.

#### Scenario: Review command gets runner facts
- **WHEN** A staging run on a devops-cli commit gets a plan that adds `devops review` to the Job.
- **THEN** The planner context contains the image tool list, the `NOT_IN_RUNNER` entry of each program with its reason text and the pod security settings.

#### Scenario: A commit of another repository
- **WHEN** A staging run gets a plan that cites `uv`, and the staged commit holds none of the devops-cli files.
- **THEN** The planner context contains the runner tools and the `NOT_IN_RUNNER` entries, and the run raises no `RoadmapStageError`.

### Requirement: Repository-derived facts
The context builder MUST read the Dockerfile packages and the pod security settings from the files of the staged commit only when that commit holds `src/devops_cli/roadmap/runner_tools.py`. It MUST leave each fact out when the commit lacks that path or the file of the fact. It MUST NOT copy them into a static prompt.

#### Scenario: Another repository's commit holds a Dockerfile
- **WHEN** The staged commit holds a `Dockerfile` and `k8s/devops/cronjob-runner.yaml` but no `src/devops_cli/roadmap/runner_tools.py`, and the plan cites `uv`.
- **THEN** The planner context holds no installed packages line and no pod security section, and the run raises no `RoadmapStageError`.

#### Scenario: Source move fails the test
- **WHEN** A change moves or renames `runner_tools.py`, the `Dockerfile` or the pod security manifest of the repository.
- **THEN** The test of the fact files fails and names the moved path.

### Requirement: Planner Feasibility instruction
The planner prompt SHALL tell the planner to state each needed failure class and runner capability in `## Feasibility`.

#### Scenario: Prompt names Feasibility
- **WHEN** The staging prompt includes failure or runner capability facts.
- **THEN** The prompt contains the instruction to state those facts in `## Feasibility`.
