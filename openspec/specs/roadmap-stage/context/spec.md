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
The stage context builder SHALL mark an open pull request whose title has the type `docs(spec)` or legacy `docs(openspec)` as a plan pull request.

#### Scenario: A plan pull request overlaps a cited path
- **WHEN** A test gives the builder a fake client that holds pull request 3252, titled `docs(spec): plan #3252 stage context`, which changes `src/devops_cli/roadmap/stage/stage_overlap.py`, and an item body that cites that path.
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

### Requirement: The request lists the declared issue dependencies
The stage request SHALL hold `issue_dependencies` with one entry for each blocker that the Dependencies section of the item body names (the rule of `roadmap-refine/waits`), in the order of the body. An entry SHALL hold `number` and, when the store holds the issue, `title`. The request SHALL omit the key when the body declares no dependency.

#### Scenario: Two declared dependencies
- **WHEN** the body names `#2` and `#3` as blockers in its Dependencies section, and the store holds both as items with a title
- **THEN** the request holds `[{"number": 2, "title": "..."}, {"number": 3, "title": "..."}]`

#### Scenario: An issue that the store lacks
- **WHEN** the body names `#99` and the store holds no issue 99
- **THEN** its entry is `{"number": 99}` with no `title` key

#### Scenario: No dependency in the body
- **WHEN** the body has no Dependencies section
- **THEN** the request holds no `issue_dependencies` key

### Requirement: The prompt names the declared dependencies
The prompt `roadmap_stage_change.md` SHALL state that `issue_dependencies` holds the issues of the Dependencies section and that the model writes one `dependencies` entry for each as `#<number>: <reason>`. The request holds in that key only each blocker that the Dependencies section names (the rule of `roadmap-refine/waits`), so the prompt states no blocker rule of its own.

#### Scenario: The stage prompt
- **WHEN** a test loads the prompt of the task `stage`
- **THEN** the prompt holds `issue_dependencies` and `#<number>: <reason>`

### Requirement: The first plan request holds every trusted comment of the item
The first plan request SHALL hold, under the key `comments`, every comment of the item that a person with write access or the Service App wrote, oldest first, each with its number, its author and its time: the comments of persons and the comments of the roadmap jobs. A comment of any other account SHALL NOT be in the request. The job SHALL collapse no comment.

#### Scenario: A decision of a person and a report of a job
- **WHEN** an item has a comment of the alternatives check and then a decision of a person
- **THEN** the first request holds both whole, oldest first, with `unlisted` 0, and the run offers `read_comment`

### Requirement: The comments of the first plan request fit its caps uncut
The comments SHALL take the room that the body leaves under its cap, and at most `CONST_ROADMAP_STAGE_COMMENTS_MAX_TOKENS` tokens of the context cap, at most half of it. The context SHALL lose only the tokens that the comments take past the room of the body. The newest comments SHALL come whole while they fit. Each older comment SHALL get an entry with `about`, its first line, in place of `text`, and `unlisted` SHALL count the older comments that no entry lists. No comment SHALL be cut.

#### Scenario: Comments at their caps
- **WHEN** a first request of code holds the context and the body at their caps and 41 comments, 40 of them long
- **THEN** the request stays under the limit of the tools with 512 tokens of headroom, the newest comment is whole, and the entries and `unlisted` count 41 comments

### Requirement: A staged item names the comments that its plan request held
The comment of a staged item SHALL name each comment that the plan request held whole, by its page. The key of the kept plan of an item SHALL hold the comments of persons, so a new decision makes a new plan. A comment of a job SHALL change no key.

#### Scenario: The record of the comments
- **WHEN** a staged item has a comment whose page is known
- **THEN** the comment of the staged item names that page as a comment that the plan request held whole

#### Scenario: The key of a kept plan
- **WHEN** a stage job comment and then a comment of a person come after a kept plan
- **THEN** the key stays the same after the job comment and changes after the comment of the person

### Requirement: The plan-state comment reads as made at its last edit
The jobs SHALL give their model the plan-state comment of a plan pull request at the place and the time of its last edit, because the jobs edit it in place. Every other comment SHALL keep the place and the time of its creation. The label of a comment in the index SHALL skip each hidden line, such as a marker or a key line, and SHALL show the first line of text.

#### Scenario: An edited state comment comes after an older comment
- **WHEN** a state comment made before a comment of a person was edited after it
- **THEN** the state comment comes after the comment of the person, at the time of its edit

#### Scenario: The label of a comment with a key line
- **WHEN** a comment starts with the marker of the stage job and the key line of a state comment
- **THEN** the label in the index is the first line of text after them

### Requirement: The stage context holds the text of a cited requirement
The stage context SHALL hold the name and the text of each base requirement that a cited capability, requirement name, path, command or symbol of the issue matches.

#### Scenario: A plan cites a command that a requirement names
- **WHEN** A plan cites a command that the text of one requirement of a fake spec names.
- **THEN** The stage context holds the name and the text of that requirement, and the test asserts both.

### Requirement: The stage context bounds the requirement text
The stage context SHALL cut the matching requirements at a named constant of 12 requirements and then at a named constant of 6000 characters, and each constant SHALL carry a docstring.

#### Scenario: A spec with more matches than the count bound
- **WHEN** A fake spec holds more matching requirements than the count constant allows.
- **THEN** The stage context holds exactly the count constant's number of requirements, and the test asserts the count.

#### Scenario: A match longer than the character bound
- **WHEN** The text of the matching requirements is longer than the character constant allows.
- **THEN** The requirement text of the stage context is at most the character constant's length, and the test asserts the length.

### Requirement: The stage context orders the requirement text by relevance
The stage context SHALL place a requirement whose capability or name the issue cites before a requirement whose text only a cited path, command or symbol matches.

#### Scenario: A name match outranks a text match
- **WHEN** A plan cites a requirement name and a command that the text of another requirement holds.
- **THEN** The requirement with the name match comes before the requirement with the text match, and the test asserts the order.
