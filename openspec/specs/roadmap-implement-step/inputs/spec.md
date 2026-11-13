# roadmap-implement-step/inputs Specification

## Purpose
The inputs of an implement step: the context window, the fixed inputs, the tasks file and its groups, the routes to documents, the test form of a task, and the rules of the prompt.

## Requirements

### Requirement: A step refuses an input that does not fit the window
The step SHALL count the tokens of its instructions and its user message before the first model request. When the count is more than the `context_window` of `ai.tasks.implement` minus `CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS`, the step SHALL raise `RoadmapImplementError`, SHALL name the measure and the limit in its message, and SHALL make no model request and change nothing in the checkout.

#### Scenario: Inputs over the limit
- **WHEN** the window is 4000 tokens and the packed inputs of the step measure more than the window minus the reserve
- **THEN** the step raises `RoadmapImplementError` with the exit code 1 and the error code `ROADMAP_IMPLEMENT_REFUSED`, its message holds the measured tokens and the limit, and the model gets no request

### Requirement: The inputs of a step are fixed
The user message of the model SHALL hold, in this order: the `AGENTS.md` of the checkout and the routed sections of its documents; the title, problem and criteria of the item; the `proposal.md`, `design.md` and `tasks.md` of the change; the group; its named files, packed; and, except for a fix step, the path of the `tasks.md` under "The tasks file". It SHALL hold nothing else. The change is the one folder `openspec/changes/<N>-*/`, else the step SHALL raise `RoadmapImplementError`.

#### Scenario: The first request
- **WHEN** the step runs group 1 of a change whose group 1 names `src/sample.py` and `tests/test_sample.py`, which does not exist yet
- **THEN** the first request holds the item title, the two sections of the issue, the three documents, the text of group 1, the packed `src/sample.py`, the path `openspec/changes/1-sample-change/tasks.md` and the text of `AGENTS.md` under the heading "Rules of the repository (AGENTS.md)", and it holds no text of another file

#### Scenario: A fix step
- **WHEN** a fix step builds its inputs
- **THEN** the message holds no section "The tasks file", and it holds `AGENTS.md`

#### Scenario: A missing change
- **WHEN** the checkout holds no folder `openspec/changes/7-*/`
- **THEN** the step raises `RoadmapImplementError` that names the pattern

### Requirement: The step writes nothing to GitHub and a dry run makes no request
The step SHALL read the item once and SHALL write no issue, comment, label or milestone. With `--dry-run` it SHALL make no request of any kind, SHALL start no model run, SHALL change nothing in the checkout, and SHALL return a `StepOutcome` marked as a dry run that lists the requests a run makes.

#### Scenario: A dry run
- **WHEN** `devops roadmap implement --item 7 --group 1 --dry-run` runs
- **THEN** the command exits 0, it prints the read of issue 7 and the model requests, the model gets no request, and the roadmap store sees no read

### Requirement: A step writes tasks.md back to its text before the run
After each turn of the model, the step SHALL write the `tasks.md` of the change back as it was before the run, with each task of its own group ticked that the model ticked, by position. The step SHALL tick none when the model changed the number of the tasks of the group. A fix step SHALL tick none.

#### Scenario: The model ticks two groups and edits a task of the later one
- **WHEN** the model works on group 1, ticks the tasks of groups 1 and 2, and deletes the number "2.1" from a task of group 2
- **THEN** the step reports done, and the commit holds `tasks.md` as before the run with only the tasks of group 1 ticked, and the step prints one line that names the change

#### Scenario: The model ticks a later group
- **WHEN** the model completes group 1, ticks its tasks and the tasks of group 2, and ends its run
- **THEN** the step reports done, and the commit holds group 1 ticked and group 2 unticked

#### Scenario: The model unticks an earlier group
- **WHEN** the model works on group 2, ticks its tasks, and unticks a task of group 1, which was ticked
- **THEN** the step reports done, and the commit holds group 1 as it was

#### Scenario: The model rewrites the text of a task and ticks it
- **WHEN** the model rewrites the text of task 1.1 and ticks the tasks of group 1
- **THEN** the step reports done, and the commit holds the text from before the run with the tasks of group 1 ticked

#### Scenario: The model rewrites the text in the extra turn
- **WHEN** the model rewrites the text of an unticked task in the extra turn, ticks it, and the exit checks pass
- **THEN** the step reports done, and the commit holds the text from before the run with the task ticked

#### Scenario: The model rewrites a verification command to one that passes
- **WHEN** the model replaces the command of a `Verification:` line of group 1 with a command that exits 0, and the original command exits 1
- **THEN** the step runs only the original command, reports stopped, the reason names the original command, and the checkout is reset

#### Scenario: The model adds, removes or reorders groups or tasks
- **WHEN** the model adds a group, removes a group, swaps two tasks of group 2, or adds a section outside every group, and ticks the tasks of group 1
- **THEN** the step reports done, and the commit holds the structure from before the run with group 1 ticked

#### Scenario: The model ticks part of the group
- **WHEN** the model ticks one of the two tasks of group 1, and the exit checks pass
- **THEN** the step reports done, and the commit holds both tasks of group 1 ticked

#### Scenario: The model changes the number of the tasks of its group
- **WHEN** the model adds a task to group 1 and ticks every task of the group, and the exit checks pass
- **THEN** the step restores the tasks of group 1 as they were before the run, and the commit holds them ticked

#### Scenario: The model removes or garbles the file
- **WHEN** the model removes `tasks.md`, or writes bytes that are not UTF-8 to it, and ticks nothing else
- **THEN** the step writes the file from before the run, and the job ticks the group when the exit checks pass

#### Scenario: A link or a directory in place of the file
- **WHEN** the model replaces `tasks.md` with a link to a file that holds the text to write, or with a directory
- **THEN** the step removes the link or the directory and writes the file, and the commit holds a regular file

#### Scenario: A file with CRLF or lone CR line ends
- **WHEN** the `tasks.md` has CRLF line ends, or many lone CR line ends before the groups, and the model ticks its group and a later group
- **THEN** the committed `tasks.md` keeps those line ends, the group is ticked on its own lines, and the later group is unticked

#### Scenario: A tick and nothing else
- **WHEN** the last line of group 1 ends with two spaces and the model only ticks its tasks
- **THEN** the step reports done, the commit holds the two spaces, and the step prints no line

#### Scenario: A fix step edits a task
- **WHEN** a fix step ticks a task of any group, or edits the text of a task
- **THEN** the step reports done, and the commit holds `tasks.md` as it was

#### Scenario: A tasks file that numbers a group twice
- **WHEN** the `tasks.md` of the change holds two groups with the number 2
- **THEN** the step is refused before the model runs, and the message names the change and group 2

#### Scenario: The model edits a line that is not a tick
- **WHEN** the model edits a line of the file that is not a tick
- **THEN** the step prints one line that names the change, and the step does not stop for the edit

#### Scenario: A file numbers a group twice
- **WHEN** the tasks file numbers a group twice before the run
- **THEN** the step refuses the file before it starts

### Requirement: The routes name the documents of a group
The step SHALL add the named sections of a routed document to the message when a path that the group names in a code span matches a route. Each document has its own heading and is cut to `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens. Each route SHALL name a row of the "Where to look" table of `AGENTS.md` that links its document.

#### Scenario: A group that changes a test
- **WHEN** a group names `tests/test_sample.py`
- **THEN** the message holds the section "Doubles" of `docs/TESTING.md`

#### Scenario: A group that changes only a manifest
- **WHEN** a group names only `k8s/sample.yaml`
- **THEN** the message holds a section of `k8s/README.md` and the section "Image Pins" of `docs/CLUSTER.md`, and holds nothing of `docs/TESTING.md`

#### Scenario: A route drifts from AGENTS.md
- **WHEN** a route names a "When you" cell that the table lacks, or a document that the row does not link
- **THEN** the test of the routes fails and names the route

### Requirement: The rules in the message are data and are bounded
The step SHALL cut the `AGENTS.md` text in the message to `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens. The instructions of the step SHALL stay the text of the prompt, whatever the rules hold. The prompt SHALL say that its instructions win over a rule that conflicts with them.

#### Scenario: A large AGENTS.md
- **WHEN** the `AGENTS.md` of the checkout holds more tokens than the cap
- **THEN** the rules section is cut to the cap and ends with the mark of a cut

#### Scenario: A hostile AGENTS.md
- **WHEN** the `AGENTS.md` of the checkout says to ignore the instructions and holds a heading "Your group"
- **THEN** the instructions of the step equal the prompt, and the message starts with that text under the rules heading

### Requirement: A group is a heading at the top level of the file
The step SHALL take a `## <n>. <title>` heading as the start of a group only when the heading is at the top level of `tasks.md`. A heading inside a list item or a quote SHALL be text of that item.

#### Scenario: A heading in a list item
- **WHEN** `tasks.md` holds the group 1 and, after it, a list item `- ## 2. Extra` with a task under it
- **THEN** the parsed groups are the group 1 only

#### Scenario: A heading in a quote
- **WHEN** `tasks.md` holds a quote `> ## 2. Extra` after the group 1
- **THEN** the parsed groups are the group 1 only

### Requirement: The prompt lists the local devops commands of the catalog
The prompt of the step SHALL list each command of `LOCAL_COMMANDS` in `src/devops_cli/roadmap/implement/implement_shell_policy.py` with its access class and its use, and `docs/ROADMAP_WORKFLOW.md` SHALL hold the same table. `LOCAL_COMMANDS` SHALL hold `ci test`, `ai repomap`, `ai ast`, `docs generate` and `openspec check`, and no command with the access `network`. A call of a listed command through `uv run` SHALL pass the shell policy and SHALL NOT count as a refusal.

#### Scenario: The prompt holds the table
- **WHEN** The prompt of the step is built.
- **THEN** It holds the text of `local_commands_table()` and no placeholder.

#### Scenario: The document holds the table
- **WHEN** `docs/ROADMAP_WORKFLOW.md` is read.
- **THEN** It holds the text of `local_commands_table()`.

#### Scenario: A new command is missing from the prompt
- **WHEN** A command is added to `LOCAL_COMMANDS` and the prompt file or the document does not hold it.
- **THEN** The consistency test fails and names the missing command.

#### Scenario: A listed command exists
- **WHEN** The test runs `--help` for each command of `LOCAL_COMMANDS` on the `devops` app.
- **THEN** Each command exits with status 0.

#### Scenario: A listed command is no refusal
- **WHEN** The model calls the shell tool with `uv run devops ai repomap`.
- **THEN** The command reaches the process edge, the refusal counter is unchanged, and no refusal comes back.

### Requirement: The implement prompt forbids polling
The implement prompt SHALL state that a call of the tool `run_command` waits until its command ends, up to `roadmap.implement.command_timeout_seconds` with the default of that setting, and MUST forbid polling with `sleep`, `time.sleep` or a repeated `tail`. It MUST NOT state that a shell call returns when its command ends with no limit.

#### Scenario: The prompt holds the no-poll rule
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_implement_step.md`
- **THEN** The rule names `run_command`, the wait until the command ends, the setting with its default, and sleep, time.sleep and a repeated tail as forbidden, and the prompt holds no "270"

### Requirement: A step reads the test form that a task names
The implement step SHALL read the test file and the case count that each task of its group names, and SHALL compare that count with the number of items that a pytest collection reports for the file.

#### Scenario: A task names one parametrized test over six statuses
- **WHEN** a task of the group names a test file and one parametrized test over six statuses
- **THEN** the step reads the path and the count 6 and collects the items of that file.

#### Scenario: A task names no test form
- **WHEN** no task of the group names a parametrized test
- **THEN** the step runs no form check and ticks the tasks of the group when its exit checks pass.

### Requirement: A step refuses a test that does not match the form of its task
The implement step SHALL refuse a test whose collected item count differs from the count that its task names, and SHALL refuse a named parametrized test that the collection reports as one item. The step MUST keep such a task unticked.

#### Scenario: Eleven collected items for six named cases
- **WHEN** the task names six cases and the collection reports eleven items
- **THEN** the step stops the group, keeps its tasks unticked, and names the count 6 and the count 11 in its reason.

#### Scenario: One collected item for a named parametrized test
- **WHEN** the task names a parametrized test and the collection reports one item
- **THEN** the step stops the group and asks for one parametrized item for each case.

#### Scenario: A repair turn follows the first refusal
- **WHEN** the form check refuses the test and a repair round is left
- **THEN** the step runs one repair turn that may change the named test file, and checks the form again.

### Requirement: The issue section of a step holds the refined criteria and no HTML comment
The issue section of the user message of a step SHALL hold the title of the item and each top-level section of the issue body whose heading is `Problem or Motivation`, `Problem statement` or `Acceptance criteria`, or starts with `Requirement:`, each with its deeper headings, in the order of the body. The section SHALL hold no top-level HTML comment block of the body. An issue body that holds none of these sections SHALL give its whole text with no top-level HTML comment block.

#### Scenario: A body that refine wrote its criteria into
- **WHEN** the body holds a `### Acceptance criteria` heading that two `### Requirement:` sections with their `#### Scenario:` lines follow, at the same level
- **THEN** the issue section holds both requirement headings, their text and their `WHEN` and `THEN` lines after the `Acceptance criteria` heading

#### Scenario: The refine markers after a criteria list of a person
- **WHEN** the body holds a `## Acceptance criteria` list and then the refine start marker and the `checked-at` comment before `## Proposed design`
- **THEN** the issue section holds the list items and no `<!--`

#### Scenario: A body with no wanted section
- **WHEN** the body holds only the sections of the bug form and the alternatives block
- **THEN** the issue section holds the whole body without the two marker lines of the alternatives block

### Requirement: The implement prompt gives the count of extra turns
The implement prompt SHALL state that a step has at most `roadmap.implement.repair_rounds` extra turns, with the default of that setting, and that each failed check or hook takes one. It MUST NOT promise one more turn for an error of `ruff check` or `mypy`.

#### Scenario: The prompt names the setting of the extra turns
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_implement_step.md`
- **THEN** The prompt names `roadmap.implement.repair_rounds` with its default and holds no promise of one more turn
