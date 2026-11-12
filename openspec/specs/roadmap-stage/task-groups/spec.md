# roadmap-stage/task-groups Specification

## Purpose
The form of the task groups of a plan: their files, kinds, tasks and text, the measure of each group against the step budget, the split of a group over it, and the files that a group must not write.

## Requirements

### Requirement: The job measures each task group
The job SHALL measure each task group with tiktoken: the tokens of the group's instructions, the item, the change folder, the `AGENTS.md` of the repository, the routed sections of its documents, and the files that the tasks of the group name in code spans, each packed as the implement step packs it, at most `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens. The budget SHALL be `roadmap.stage.step_tokens`, default 64000, and `--step-tokens` SHALL override it for one run.

#### Scenario: A group is measured
- **WHEN** the model gives a group whose task names a file of the repository
- **THEN** the comment on the issue gives the group's measure, and that measure is more than the tokens of the file packed

#### Scenario: A large file counts as the step reads it
- **WHEN** a task of a group names one file that holds more tokens than the budget
- **THEN** the group measure is under the budget, and the job asks the model for no split

#### Scenario: A file that no task names
- **WHEN** the `Reads:` line of a group lists a file that no task of the group names
- **THEN** the file adds no token to the measure, as the step does not read it

#### Scenario: The rules count
- **WHEN** the repository holds an `AGENTS.md` and a group names `tests/test_sample.py`
- **THEN** the measure of the group holds the tokens of the `AGENTS.md` and of the routed sections of `docs/TESTING.md`

### Requirement: A group over the budget is split once or stops the item
A group over the budget SHALL go back to the model once with its measure and the ask to split it. The job SHALL ask for a split once for each item, also when a corrected reply is over the budget again. A group still over the budget SHALL stop the item: the job posts a comment that names the group and its measure, records `stage.needs_split`, and makes no branch.

#### Scenario: Every group is under the budget
- **WHEN** the model gives three groups and the measure of each is under the budget
- **THEN** the job asks the model once, and the comment lists the three groups with their measures

#### Scenario: A group is split
- **WHEN** one group is over the budget and the second reply splits it into two groups under the budget
- **THEN** the job stages the item with the groups of the second reply

#### Scenario: A corrected reply is over the budget
- **WHEN** the first reply is split, the split fails the validation, and the corrected reply is over the budget
- **THEN** the job stops the item as over the budget and asks the model for no second split, so it made three calls

#### Scenario: A group stays over the budget
- **WHEN** one group is over the budget after the second reply
- **THEN** the job posts a comment that names the group and its measure, records `stage.needs_split`, pushes no branch and opens no pull request

### Requirement: A task group names its files
A task group of the reply SHALL name at least one path in `changes`. A path SHALL hold no backtick and no control character. `reads` MAY be empty. Every path of `creates` SHALL be a path of `changes`.

#### Scenario: A group with no changed file
- **WHEN** the reply holds a group with an empty `changes`
- **THEN** the reply fails the schema

#### Scenario: A path that breaks the line
- **WHEN** the reply holds a path with a new line or a backtick
- **THEN** the reply fails the schema

### Requirement: A task group has the text of its tasks
A task group of the reply SHALL have a text in `title` with at least one character after its whitespace is stripped. It SHALL have a text in `implementation` with at least one character that is no space and no full stop. `test` and `documentation`, when set, SHALL have the same. `verify` and `process`, when set, SHALL have at least one character after their whitespace is stripped. `test`, `verify`, `process` and `documentation` MAY be null.

#### Scenario: A blank text
- **WHEN** the reply holds a group whose `documentation` is blank
- **THEN** the reply fails the schema

#### Scenario: A text of only full stops
- **WHEN** the reply holds a group whose `documentation` is `...`
- **THEN** the reply fails the schema, as a blank text does

#### Scenario: A group with no documentation
- **WHEN** the reply holds a group whose `documentation` is null
- **THEN** the reply passes the schema

### Requirement: A task group renders without stray punctuation
The group SHALL render as the line `Reads: <paths>. Changes: <paths>.` where an empty `reads` shows `none`, and a created path shows `(new)` after it. A rendered group SHALL hold no double full stop and no task that starts with a comma.

#### Scenario: A group with no reads
- **WHEN** a group has an empty `reads` and a `changes` that holds `src/devops_cli/sample.py`
- **THEN** its line is ``Reads: none. Changes: `src/devops_cli/sample.py`.``

#### Scenario: A created path
- **WHEN** a group has `tests/test_sample.py` in `changes` and in `creates`
- **THEN** its line shows ``Changes: `tests/test_sample.py` (new).``

#### Scenario: A task ends in a full stop
- **WHEN** the `implementation` of a group ends in a full stop or in several
- **THEN** the task renders with no full stop before the comma

### Requirement: A stop record counts only for the measure that made it
The job SHALL record `stage.file_cap`, the file cap of the measure, with `stage.needs_split`. The job SHALL leave an item out for a recorded split only when `stage.file_cap` is the file cap of now. The job SHALL clear `stage.file_cap` when it stages the item.

#### Scenario: A record of an earlier measure
- **WHEN** the record of an item holds `stage.needs_split` and no `stage.file_cap`, or another one
- **THEN** the job does not leave the item out for the record

#### Scenario: A record of the measure of now
- **WHEN** the record of an item holds `stage.needs_split` and the `stage.file_cap` of now
- **THEN** the plan leaves the item out and says why, and `--item` stages it

### Requirement: A task group has a kind
A task group of the reply SHALL have a `kind`: `behavior` or `other`. A `behavior` group SHALL have a `test` and a `verify`, no `process`, and a path under `src/` in `changes`. An `other` group SHALL have no `test`, and exactly one of `verify` and `process`. The reply that breaks a rule SHALL fail the schema, and the problem text SHALL name each rule it breaks.

#### Scenario: A test on an other group
- **WHEN** the reply holds an `other` group with a `test`
- **THEN** the reply fails the schema, and the model gets the problem text

#### Scenario: A behavior group with no test
- **WHEN** the reply holds a `behavior` group whose `test` is null
- **THEN** the reply fails the schema

#### Scenario: A behavior group that changes no source
- **WHEN** the reply holds a `behavior` group whose `changes` hold only `docs/TESTING.md`
- **THEN** the reply fails the schema

#### Scenario: An other group with no proof
- **WHEN** the reply holds an `other` group with no `verify` and no `process`
- **THEN** the reply fails the schema

### Requirement: A task group renders the tasks of its kind
A `behavior` group SHALL render `n.1` as its failing test, `n.2` as its implementation, and `n.3` as its documentation when `documentation` is set. An `other` group SHALL render `n.1` as its implementation with its `verify` or its `process`, and `n.2` as its documentation when `documentation` is set. A task with a command SHALL write it on a line `- Verification: ` under the task, as a code span that `step_files` reads. A group with no `documentation` SHALL render no documentation task.

#### Scenario: A deletion that keeps behavior
- **WHEN** an `other` group deletes a definition and its `verify` is a `git grep` that must print nothing
- **THEN** its first task names the deletion, the line under it holds the `git grep` and says "passes", and no task asks for a test or says "fails on the base"

#### Scenario: A manual check
- **WHEN** an `other` group has a `process`
- **THEN** its first task holds the steps of the process, and it has no `Verification:` line

#### Scenario: A behavior group
- **WHEN** a `behavior` group has a `test`
- **THEN** its first task is the test, and the line under it holds the `verify` command and says "fails on the base"

#### Scenario: The step reads the command
- **WHEN** the text that `group_text` writes for a group with a `verify` is parsed with `parse_task_groups`
- **THEN** `verification_commands` of the parsed group holds the `verify` of the group

#### Scenario: A group with documentation
- **WHEN** a group has a `documentation` task and changes `src/devops_cli/commands/pr.py`
- **THEN** its last task holds the command that regenerates the documents, and its `Verification:` line holds `uv run devops ci docs`

### Requirement: The prompts and the validator name the same kinds
The stage prompt and the split prompt SHALL name each value of the kind and each field of a task group. The implement prompt SHALL tell the step to write the failing test first only when its group has a test task.

#### Scenario: A kind the prompt does not name
- **WHEN** a value of the kind is absent from the stage prompt
- **THEN** the guard test fails

### Requirement: A text of a group stays on one line
The `title`, `test`, `implementation`, `documentation`, `verify` and `process` of a task group, and the `criterion` and the `reason` of a criterion, SHALL be written to `tasks.md` on one line, and a text set after validation SHALL be validated again. A line break in one of them SHALL add no line, no task, no group and no `Verification:` line.

#### Scenario: A line break and a command
- **WHEN** the `implementation` of a group holds a line break and a line `- Verification: ` with a command
- **THEN** the `verification_commands` of the parsed group are the `verify` of the group and the check of the documents, and no more

#### Scenario: A line break in a title
- **WHEN** the `title` of a group holds a blank line and a line `- [ ] 9.9 Extra`
- **THEN** `tasks.md` holds one group and the task list is that of the group

#### Scenario: A line break in the reason of a criterion
- **WHEN** the `reason` of a `pending-person` criterion holds a line `## 2. Extra`
- **THEN** `tasks.md` holds one group

#### Scenario: Any line terminator
- **WHEN** a text of a group holds a heading after any character that ends a line in markdown or in Python, such as `\r`, `\x85` or U+2028
- **THEN** `tasks.md` holds one group, and the text holds one space in place of the character

#### Scenario: A text set after validation
- **WHEN** the `implementation` of a validated group is set to a text with a line break and a `Verification:` line
- **THEN** the text is on one line, and the group renders no extra command

### Requirement: A verify command holds no backtick
`form_problems` SHALL give a problem for a `verify` command that holds a backtick, and the problem SHALL say that it holds a backtick. A command that also has a wrong form SHALL get the problem of its form in the same run.

#### Scenario: A backtick in a command
- **WHEN** the `verify` of a group is ``uv run devops ci test `x` ``
- **THEN** `form_problems` gives one problem, and it says that the command holds a backtick

#### Scenario: A backtick and a wrong form
- **WHEN** the `verify` of a group is ``pytest `x` ``
- **THEN** `form_problems` gives two problems: the backtick, and the form to use

### Requirement: A verify command keeps its spaces
The `verify` of a task group SHALL be written on one line by joining its lines with one space, and SHALL keep every other space of the command.

#### Scenario: Two spaces in a word
- **WHEN** the `verify` is `! git grep -n 'a  b'` and a line break and `src/`
- **THEN** the `verify` of the group is `! git grep -n 'a  b' src/`

### Requirement: A split reply is checked for the form of its commands
The job SHALL check the groups of a split reply for the form of their `verify` commands, as it checks the groups of a plan, and SHALL send a reply with a problem back to the model as a refused reply.

#### Scenario: A split group with two commands
- **WHEN** a split group has a `verify` of ``uv run devops ci test tests/x.py` and `git push origin HEAD``
- **THEN** the reply goes back to the model with the `verify` problem, and the model is asked once more

### Requirement: A task of a group holds more than one word
`form_problems` SHALL give a problem for each `test`, `implementation` or `documentation` text of a group that holds one word or less, with a code span counted as one word. The problem SHALL name the group by its number and its title, and the part of the text.

#### Scenario: A bare filename as the first task
- **WHEN** the `test` of a behavior group is `src/devops_cli/roadmap/stage/stage_form.py`
- **THEN** `form_problems` gives one problem, and it names the group and the part `test`

#### Scenario: A single word as the work
- **WHEN** the `implementation` of a group is `Refactor`
- **THEN** `form_problems` gives one problem that names the part `implementation`

#### Scenario: A code span alone
- **WHEN** the `test` of a group is a path in a code span
- **THEN** `form_problems` gives one problem

#### Scenario: A task with a verb and an object
- **WHEN** the `test` of a group is `Add a test in tests/roadmap/stage/test_roadmap_stage_form.py for a bare filename task`
- **THEN** `form_problems` gives no problem for the task

### Requirement: The group measure and the Job use one token counter
The stage SHALL count the tokens of a task group with the same tiktoken encoding as the implement Job, and SHALL raise an error that names the missing tiktoken cache when the encoding cannot be loaded.

#### Scenario: Both paths count the same text
- **WHEN** The stage and the implement Job count the same task-group text and the tiktoken cache is present
- **THEN** Both give the same token count

#### Scenario: The token cache is missing
- **WHEN** A plan run measures a task group and the tiktoken cache is missing
- **THEN** The run fails with an error that names the missing cache and no character count is used

### Requirement: A created file counts its estimated lines
The stage SHALL add 32 tokens for each estimated line of a path in the `creates` of a task group to the token count of that group, and SHALL refuse a group whose `creates` path has no line estimate with an error that names the path.

#### Scenario: A group creates a 1,500-line file
- **WHEN** A task group has a `creates_lines` entry with a 1,500-line estimate and no other input
- **THEN** The stage counts the group as at least 48,000 tokens and refuses it as over a 40,000-token budget

#### Scenario: A creates path has no estimate
- **WHEN** A task group creates a file and the reply gives no line estimate for that path
- **THEN** The stage refuses the group with an error that names the path

### Requirement: The staging prompt states the budget and the estimate rule
The staging prompt SHALL name the `budget` of the run as the most tokens of one step and the rule that each `creates` path carries a line estimate.

#### Scenario: The prompt states both limits
- **WHEN** The staging prompt of a plan run is loaded
- **THEN** It names the `budget` of the run and the line-estimate rule for each `creates` path

### Requirement: A task group writes no living spec
A `StageGroup` SHALL reject a path under `openspec/specs/` in `changes` or in `creates`, with a validation error that names the path and says that only `openspec archive` writes living specs. A path under `openspec/specs/` in `reads` SHALL stay accepted.

#### Scenario: A group lists a living spec in changes
- **WHEN** A `StageGroup` lists `openspec/specs/config-commands/spec.md` in `changes` and `creates`
- **THEN** validation fails, and the error names `openspec/specs/config-commands/spec.md` and says that only `openspec archive` writes living specs

#### Scenario: A group lists a living spec in creates
- **WHEN** A `StageGroup` lists `openspec/specs/new-capability/spec.md` in `changes` and `creates`
- **THEN** validation fails, and the error names `openspec/specs/new-capability/spec.md`

#### Scenario: A group writes a source file and reads a living spec
- **WHEN** A `StageGroup` lists `src/devops_cli/sample.py` in `changes` and `openspec/specs/config-commands/spec.md` in `reads`
- **THEN** validation succeeds

### Requirement: The stage prompt states the living-spec rule
The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL state that a task group never puts a path under `openspec/specs/` in `changes` or in `creates`, and that `openspec archive` writes living specs.

#### Scenario: The prompt holds the living-spec rule
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the text says that a task group must not change or create a file under `openspec/specs/`, and that `openspec archive` writes living specs

### Requirement: A task group writes no file under openspec/changes
A `StageGroup` SHALL reject a path in `changes` or `creates` that is `openspec/changes` or that starts with `openspec/changes/`, and SHALL accept such a path in `reads`.

#### Scenario: A change-folder path in changes
- **WHEN** a `StageGroup` sets `changes` to `openspec/changes/3060-model-tier-ladder/proposal.md`
- **THEN** validation fails with a message that names that path and the rule

#### Scenario: A change-folder path in creates
- **WHEN** a `StageGroup` sets `creates` and `changes` to `openspec/changes/3060-model-tier-ladder/tasks.md`
- **THEN** validation fails with a message that names that path

#### Scenario: The change folder itself
- **WHEN** a `StageGroup` sets `changes` to `openspec/changes`
- **THEN** validation fails

#### Scenario: A change-folder path in reads
- **WHEN** a `StageGroup` sets `reads` to `openspec/changes/3060-model-tier-ladder/proposal.md` and changes `src/devops_cli/roadmap/stage/stage_change.py`
- **THEN** validation succeeds

### Requirement: The path check reports a change-folder path
`path_problems` SHALL report a group path that is `openspec/changes` or that starts with `openspec/changes/`, in the place where the group names it, so that `check_proposal` refuses a recorded plan that skipped the schema.

#### Scenario: A recorded group that creates a change file
- **WHEN** `path_problems` runs on a group built without validation that creates `openspec/changes/3060-model-tier-ladder/proposal.md`
- **THEN** it returns one problem that names the group, the path and the rule

#### Scenario: A recorded group that only reads a change file
- **WHEN** `path_problems` runs on a group that reads `openspec/changes/3060-model-tier-ladder/proposal.md` in a tree that holds that file
- **THEN** it returns no problem

### Requirement: The stage prompt forbids a change-folder write
The roadmap stage prompt SHALL state that an implementation group must not change or create a path under `openspec/changes/`.

#### Scenario: The prompt states the rule
- **WHEN** the prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` is read
- **THEN** it holds a sentence that names `openspec/changes/` and forbids the change and the creation of a path under it

### Requirement: The tuicr bullet needs a source change
The task renderer SHALL add the tuicr review bullet only when at least one task group changes a path under `src/`.

#### Scenario: A plan that changes no source omits the bullet
- **WHEN** a plan has groups that change no path under `src/`
- **THEN** the rendered `tasks.md` holds no bullet that starts with `Pending a person: review the diff in tuicr`.

#### Scenario: A plan that changes source gets the bullet
- **WHEN** a plan has one group that changes `src/devops_cli/roadmap/stage/stage_change.py`
- **THEN** the rendered `tasks.md` holds the tuicr review bullet.

### Requirement: An empty workflow follow-up section is omitted
The task renderer SHALL write the `## Workflow follow-up` heading only when it holds a bullet.

#### Scenario: No follow-up bullet leaves no section
- **WHEN** a plan has no workflow follow-up bullet
- **THEN** the rendered `tasks.md` holds no `## Workflow follow-up` heading.

### Requirement: A document task starts with the Edit verb
The task renderer MUST prepend the fixed verb `Edit` to a documentation text whose first word is a path, and MUST write that path in a code span. A path is a word that holds `/` or ends in a dot and letters.

#### Scenario: A root document gets the Edit verb
- **WHEN** a group supplies the documentation text `SECURITY.md`
- **THEN** the rendered task starts with `Edit` and names `SECURITY.md` in a code span.

#### Scenario: A nested document in a code span gets the Edit verb
- **WHEN** a group supplies the documentation text `` `docs/TESTING.md` and `docs/SDLC.md` ``
- **THEN** the rendered task reads `Edit` followed by the two paths in code spans.

### Requirement: A document task keeps its own verb
The task renderer MUST keep a documentation text whose first word is not a path unchanged.

#### Scenario: An existing verb has no double verb
- **WHEN** a group supplies the documentation text `Document the fix in `docs/TESTING.md``
- **THEN** the rendered task starts with `Document` and holds no `Edit Document`.

### Requirement: The documentation field starts with an imperative verb
The stage prompt SHALL state that the `documentation` field starts with an imperative verb, names each document in a code span, and is `null` when the step changes no document.

#### Scenario: The prompt states the documentation rule
- **WHEN** a test reads the stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the prompt states the imperative verb rule, the rule that names each document, and the `null` rule for a step that changes no document.

### Requirement: A documentation task runs the regeneration step for a command change
A documentation task SHALL end with the command `uv run devops docs generate` only when the group changes a path under `src/devops_cli/commands/` or `src/devops_cli/lang/`. A documentation task of any other group SHALL hold the documentation text and no regeneration command.

#### Scenario: A group that changes a document only
- **WHEN** a group has a `documentation` task and changes only `SECURITY.md`
- **THEN** its last task holds the documentation text with no regeneration command, and its `Verification:` line holds `uv run devops ci docs`

### Requirement: Two tasks of a plan state different work
`check_proposal` SHALL refuse two tasks whose normalized work text is the same, and SHALL name both task numbers and the group or groups of those tasks.

#### Scenario: Duplicate task in one group
- **WHEN** group 2 holds task 2.1 and task 2.3 with the same normalized work text
- **THEN** `check_proposal` returns a problem that names task 2.1, task 2.3 and group 2

#### Scenario: Duplicate task across two groups
- **WHEN** group 2 task 2.1 and group 4 task 4.2 hold the same normalized work text
- **THEN** `check_proposal` returns a problem that names task 2.1, task 4.2, group 2 and group 4

#### Scenario: Two tasks share a verification command
- **WHEN** group 3 task 3.1 and task 3.2 hold different work text and the same `Verification:` command
- **THEN** `check_proposal` returns no duplicate-task problem for task 3.1 and task 3.2

#### Scenario: A documentation task repeats an implementation task
- **WHEN** an `other` group 3 holds task 3.1 that adds a paragraph and task 3.2 that adds the same paragraph with the docs command
- **THEN** `check_proposal` returns a duplicate-task problem that names task 3.1 and task 3.2

#### Scenario: Work text that differs only in spacing and case
- **WHEN** group 1 task 1.1 and task 1.2 hold the same words with different runs of spaces and different case
- **THEN** `check_proposal` returns a duplicate-task problem for task 1.1 and task 1.2

### Requirement: The stage writes the mark before each verification command
The stage job SHALL write the code span of each `Verification:` line it writes as `$ ` followed by the command, for a task that tests, a task that implements and a task that documents, so that the implement step reads the command.

#### Scenario: A staged group
- **WHEN** the stage job writes the tasks of a `behavior` group with the `verify` command `uv run devops ci test tests/test_sample.py`
- **THEN** the `Verification:` line of each of its first two tasks holds the code span `$ uv run devops ci test tests/test_sample.py`, and `parse_task_groups` reads the command without the mark

### Requirement: A task group has the kind manifest
The stage group schema SHALL accept a group of kind `manifest` that has a `test`, an `implementation` and a `verify`, and no `process`.

#### Scenario: A manifest group validates
- **WHEN** A group has `kind: manifest`, a `test` that names `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml` in a code span, an `implementation`, and `verify: uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`.
- **THEN** `StageGroup.model_validate` returns a group whose `kind` is `manifest` and whose `process` is `None`.

#### Scenario: A manifest group has no case task
- **WHEN** A group has `kind: manifest` and `test: null`.
- **THEN** the validation error names the kind `manifest` and the missing `test`.

### Requirement: A manifest group renders its case first
`group_text` SHALL render the case task of a `manifest` group first, with `fails on the base` under it, and the work of the group second.

#### Scenario: The case comes before the work
- **WHEN** `group_text` renders a `manifest` group whose `test` names `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml` and whose `verify` is `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`.
- **THEN** the first task line holds the case text and a `Verification:` line that ends with `fails on the base`, and the second task line holds the work.

### Requirement: A case path forces the manifest kind
The stage form check MUST refuse a group of kind `other` that creates or changes a case path, and MUST name the kind `manifest` in the problem.

#### Scenario: An other group changes a promtool case
- **WHEN** An `other` group lists `tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml` in `changes`.
- **THEN** `form_problems` returns one problem that names `other`, `manifest` and the path.

#### Scenario: A manifest group changes the case
- **WHEN** A `manifest` group lists that path in `changes`, its `test` names the path in a code span, and its `verify` is `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`.
- **THEN** `form_problems` returns no problem for the group.

### Requirement: The manifest verify runs a case of the group
The stage form check MUST refuse a `manifest` verify command that is not `uv run devops ci test ` followed by a path of the group.

#### Scenario: A devops command that runs no case
- **WHEN** A `manifest` group gives `uv run devops ci mutate tests/prometheus` as its verify command.
- **THEN** `form_problems` returns one problem that names the command and the `uv run devops ci test` form.

### Requirement: The planner prompt names the manifest kind
The planner prompt SHALL name the `manifest` kind, its case-first rule and its verify rule.

#### Scenario: Prompt and kinds agree
- **WHEN** the prompt-vs-rules test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md` and the names of `GroupKind`.
- **THEN** the test finds `manifest` in both and passes.

### Requirement: A split reply is judged by every gate of the first reply
The job SHALL judge the proposal that a split gives with the same call as the first reply, with the same arguments. A gate that finds a problem in the new groups SHALL send the reply back to the model with that problem, as it does for the first reply.

#### Scenario: A split changes a trigger path and runs no replay
- **WHEN** The first reply passes the gates, one group is over the budget, and the split gives a group that changes `src/devops_cli/roadmap/stage/stage_form.py` with no task that runs the replay of the stage job
- **THEN** the job sends the reply back with the problem of the `eval-replay` gate and makes three model calls

#### Scenario: A split drops a path of What Changes
- **WHEN** The first reply names a source file in What Changes and in a group, and the split gives groups that list that file nowhere
- **THEN** the job sends the reply back with the problem of the `what-changes` gate

#### Scenario: A split moves one module of a prefix
- **WHEN** The split gives a group that moves one module of a prefix to a subpackage and no group names the other module of the prefix in `changes`
- **THEN** the job sends the reply back with the problem of the `move-prefix` gate

#### Scenario: A split names a registry item and not its test module
- **WHEN** The split gives a group whose task names a registry item that a test module declares, and no task names the declared test module
- **THEN** the job sends the reply back with the problem of the `registry` gate
