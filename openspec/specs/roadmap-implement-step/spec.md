# roadmap-implement-step Specification

## Purpose
What `devops roadmap implement` reads, runs, checks, commits and reports when it runs one task group of a staged change in one bounded context, so that the exit of a step is a fact that the step checks and not a claim of the model.

## Requirements

### Requirement: A step commits its group when the exit checks pass
`devops roadmap implement --item N --group n` SHALL run one agent on group n of the `tasks.md` of the change of item N in the checkout. When the agent returns and every exit check passes, the step SHALL commit the checkout as `<group title> (#N)` and report done with the commit. A step SHALL end done in no other way.

#### Scenario: The agent writes the test and the code
- **WHEN** the model writes a test file and a source file, ticks the tasks of group 1, and ends its run, and the verification command, `ruff` and `mypy` exit 0
- **THEN** the step reports done, the checkout holds one new commit titled `The first group (#7)`, that commit holds the three files, and the tasks of group 1 are ticked in the commit

### Requirement: A failed exit check stops the step and resets the checkout
The exit checks SHALL run in this order: the group changed only in its checkboxes and no other group changed, each verification command passes, the static checks pass, and every task of the group is ticked. The step SHALL stop at the first check that fails, name it as the reason, make no commit, and reset the checkout. A task left unticked after the first three checks first gets the extra turn of the requirement "A step asks once for the missing ticks".

#### Scenario: A verification command fails
- **WHEN** the model ends its run with the files written and the tasks ticked, and the verification command exits 1
- **THEN** the step reports stopped, the reason names the command and its exit status, the checkout holds no new commit, and the written files are gone

#### Scenario: A static check fails
- **WHEN** the verification command exits 0 and `ruff check` exits 1 on the changed file
- **THEN** the step reports stopped with the reason that `ruff check` failed, makes no commit and resets the checkout

#### Scenario: A task stays unticked
- **WHEN** the model ends its run and leaves a task of the group unticked, the verification command and the static checks exit 0, and the extra turn leaves the task unticked
- **THEN** the step reports stopped, the reason names the unticked task, and the checkout is reset

#### Scenario: A task stays unticked and a verification command fails
- **WHEN** the model ends its run and leaves a task of the group unticked, and the verification command exits 1
- **THEN** the step reports stopped with the reason that names the command and its exit status, the model gets no extra turn, and the checkout is reset

#### Scenario: The model changes another group
- **WHEN** the model ticks a task of group 2 while it works on group 1
- **THEN** the step reports stopped, the reason names group 2, and the checkout is reset

#### Scenario: A task that the agent removes
- **WHEN** the model removes a task of group 1 from the `tasks.md` and ticks the others
- **THEN** the step reports stopped with the reason that the tasks of group 1 changed, and the checkout is reset

#### Scenario: A tasks file that is gone
- **WHEN** the model removes the `tasks.md` of the change
- **THEN** the step reports stopped with the reason that the tasks of group 1 changed, and the checkout is reset

#### Scenario: A verification command outside the allowlist
- **WHEN** a Verification line of the group names `curl http://example.com`
- **THEN** the step reports stopped, the reason names `curl` as not allowed, the command does not run, and the checkout is reset

### Requirement: A step makes the only commit
The first exit check SHALL be that `HEAD` is still the commit where the step started. A `tasks.md` that is missing or is not UTF-8 text SHALL count as a change to the tasks of the group.

#### Scenario: A commit by the agent
- **WHEN** the agent commits its work with `git`, and ticks the tasks
- **THEN** the step reports stopped with the reason that `HEAD` moved, makes no commit, and the checkout is back at the commit where the step started

### Requirement: The verification commands of a group are the code spans of its Verification lines
The verification commands of a group SHALL be the code spans of the `Verification:` lines of its tasks, each one once, in the order of the file. The step SHALL run each one in the checkout, and SHALL refuse to run one whose first word is not a program of the verification list: the shell allowlist, `openspec` and `devops`.

#### Scenario: Two lines name one command
- **WHEN** two tasks of the group name `uv run devops ci test tests/test_sample.py` and the second names `uv run devops docs check` as well
- **THEN** the step runs `uv run devops ci test tests/test_sample.py` once and `uv run devops docs check` once, in that order

### Requirement: A step refuses an input that does not fit the window
The step SHALL count the tokens of its instructions and its user message before the first model request. When the count is more than the `context_window` of `ai.tasks.implement` minus `CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS`, the step SHALL raise `RoadmapImplementError`, SHALL name the measure and the limit in its message, and SHALL make no model request and change nothing in the checkout.

#### Scenario: Inputs over the limit
- **WHEN** the window is 4000 tokens and the packed inputs of the step measure more than the window minus the reserve
- **THEN** the step raises `RoadmapImplementError` with the exit code 1 and the error code `ROADMAP_IMPLEMENT_REFUSED`, its message holds the measured tokens and the limit, and the model gets no request

### Requirement: A step refuses a checkout with uncommitted changes
The step SHALL refuse to start when `git status --porcelain` lists a change in the checkout, because a failed step resets the checkout. It SHALL raise `RoadmapImplementError` and make no model request.

#### Scenario: A dirty checkout
- **WHEN** the checkout holds an untracked file
- **THEN** the step raises `RoadmapImplementError` that names the checkout, the model gets no request, and the file stays

### Requirement: The inputs of a step are fixed
The user message of the model SHALL hold the title, problem statement and acceptance criteria of the item, the `proposal.md`, `design.md` and `tasks.md` of the change, the group, the files that the group names, packed, and, except for a fix step, the path of the `tasks.md` under the heading "The tasks file". It SHALL hold nothing else. The change is the one folder `openspec/changes/<N>-*/` of the checkout, and the step SHALL raise `RoadmapImplementError` when there is none or more than one.

#### Scenario: The first request
- **WHEN** the step runs group 1 of a change whose group 1 names `src/sample.py` and `tests/test_sample.py`, which does not exist yet
- **THEN** the first request holds the item title, the two sections of the issue, the three documents, the text of group 1, the packed `src/sample.py` and the path `openspec/changes/1-sample-change/tasks.md`, and it holds no text of another file

#### Scenario: A fix step
- **WHEN** a fix step builds its inputs
- **THEN** the message holds no section "The tasks file"

#### Scenario: A missing change
- **WHEN** the checkout holds no folder `openspec/changes/7-*/`
- **THEN** the step raises `RoadmapImplementError` that names the pattern

### Requirement: The shell tool admits only the project's programs
The shell tool of the agent SHALL run a command only when its first word is `git`, `uv`, `ruff` or `mypy`, and the command holds none of the operators that start a second command. Any other command SHALL come back to the model as a refusal, and the run SHALL go on. The shell SHALL run with `HOME` set to a temporary directory of the step, so that the configuration and credentials of the user's home do not reach it. The shell is no security boundary.

#### Scenario: A program outside the list
- **WHEN** the model calls the shell tool with `curl http://example.com`, and then ends its run
- **THEN** the call returns the refusal that `curl` is not in the allowed list, no process starts, and the run ends with the last message of the model

#### Scenario: The devops command
- **WHEN** the model calls the shell tool with `devops gh api -X POST repos/example/roadmap/issues`
- **THEN** the call returns the refusal that `devops` is not in the allowed list, and no process starts

#### Scenario: A second command
- **WHEN** the model calls the shell tool with `git status; curl http://example.com`
- **THEN** the call returns a refusal that names the operator, and no process starts

### Requirement: A run that reaches a limit ends stopped
`UsageLimits` SHALL cap a run at `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` model requests and `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` tool calls, and the extra turn for the ticks SHALL count against them. A run that reaches a limit, or breaks the rules of its tools past their retries, SHALL end as stopped with the class name of the pydantic-ai error as the reason, and the step SHALL reset the checkout. The agent SHALL have no `delegate_task` tool.

#### Scenario: A model that never ends
- **WHEN** the model calls a tool in every reply
- **THEN** the step reports stopped with the reason `UsageLimitExceeded`, the model got `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests at most, and the checkout is reset

#### Scenario: A model that calls too many tools
- **WHEN** the model calls more tools than `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` before it reaches the request limit
- **THEN** the step reports stopped with the reason `UsageLimitExceeded`, and the checkout is reset

#### Scenario: The tools of the agent
- **WHEN** the step makes its first request
- **THEN** the function tools offered are `read_file`, `write_file`, `edit_file`, `list_files`, `grep` and `shell`

#### Scenario: The extra turn shares the budget
- **WHEN** the first turn used all but one of the model requests and the extra turn needs two
- **THEN** the step reports stopped with the reason `UsageLimitExceeded`, and the model got `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests at most over both turns

### Requirement: The step writes nothing to GitHub and a dry run makes no request
The step SHALL read the item once and SHALL write no issue, comment, label or milestone. With `--dry-run` it SHALL make no request of any kind, SHALL start no model run, SHALL change nothing in the checkout, and SHALL return a `StepOutcome` marked as a dry run that lists the requests a run makes.

#### Scenario: A dry run
- **WHEN** `devops roadmap implement --item 7 --group 1 --dry-run` runs
- **THEN** the command exits 0, it prints the read of issue 7 and the model requests, the model gets no request, and the roadmap store sees no read

### Requirement: The outcome is a structured report
The step SHALL return a `StepOutcome` with the status (done or stopped), the reason, the last message of the agent, the commit, and the requests and tokens that the run spent. The command SHALL print it as a table, or as JSON with `--format json`, and SHALL exit 1 when the status is stopped. The step SHALL record the spend of the run as one record of the spend ledger.

#### Scenario: A stopped step as JSON
- **WHEN** a step stops on a failed verification and the command runs with `--format json`
- **THEN** the output is one JSON object with `status` `stopped`, the reason, an empty `commit`, and the counts of requests and tokens, and the exit code is 1

#### Scenario: The spend record
- **WHEN** a step ends after two model requests
- **THEN** the spend ledger holds one record for the run with the sum of the tokens of the two replies

### Requirement: A fix step makes a failed check pass
The step SHALL accept a fix request: the name of a failed check and its log. The group of a fix step SHALL be "Make check `<name>` pass", with the verification commands of every group of the change. The inputs SHALL hold the log cut to `CONST_ROADMAP_IMPLEMENT_LOG_CHARS` characters from its end. The exit checks SHALL be those of a group, except that no task is ticked and `tasks.md` SHALL be as it was. A done fix step SHALL commit as `Make check <name> pass (#N)`.

#### Scenario: A fix step with a long log
- **WHEN** a fix request holds a log longer than the limit
- **THEN** the first message of the step holds the last characters of the log up to the limit, and the first characters are not in it

#### Scenario: The fix step ticks a task
- **WHEN** the model of a fix step changes `tasks.md`
- **THEN** the step reports stopped with the reason that the tasks changed, and the checkout is reset

### Requirement: A step asks once for the missing ticks
When the agent ends its run, the group changed only in its checkboxes, no other group changed, each verification command passes, the static checks pass, and a task of the group is unticked, the step SHALL run one more model turn. The turn SHALL continue the same conversation under the same `UsageLimits`. Its message SHALL name the path of the `tasks.md` and list the unticked tasks, and SHALL ask only for their ticks. The step SHALL run the turn at most once, and SHALL run none for a fix step.

#### Scenario: The agent forgot the ticks
- **WHEN** the model writes a test file and a source file, ends its run with the tasks of group 1 unticked, the verification command and the static checks exit 0, and the model ticks the tasks in the extra turn
- **THEN** the step reports done, the extra turn got the list of the unticked tasks, the new commit holds the test file, the source file and the ticked `tasks.md`, and the verification command ran twice

#### Scenario: The turn ticks nothing
- **WHEN** the model ends the extra turn and leaves the task unticked
- **THEN** the step reports stopped with the reason that names the unticked task, and the model got no third turn

#### Scenario: A fix step
- **WHEN** a fix step ends with a changed file and no ticks
- **THEN** the step commits the fix and the model gets no extra turn

### Requirement: The turn for the ticks changes only the tasks file
The extra turn SHALL change no file except the `tasks.md` of the change. The step SHALL check this with git, by comparing the checkout after the turn with the tree of the checkout before it, and SHALL stop with a reason that names the other paths when the turn changed any. After the turn every exit check SHALL run again. The outcome SHALL count the requests and the tokens of both turns, and the spend ledger SHALL hold the replies of both.

#### Scenario: The turn changes another file
- **WHEN** the model changes `src/sample.py` in the extra turn
- **THEN** the step reports stopped with the reason that names `src/sample.py`, makes no commit and resets the checkout

#### Scenario: The turn ticks a task of another group
- **WHEN** the model unticks a task of group 2 in the extra turn
- **THEN** the step reports stopped, the reason names group 2, and the checkout is reset

#### Scenario: The spend of two turns
- **WHEN** the first turn took two model requests and the extra turn took one
- **THEN** the outcome reports three requests, and the spend ledger holds the tokens of the three replies

### Requirement: A stopped step reports a masked diff of its discarded work
A step that ends as stopped SHALL read the diff of the work that it discards, from the commit where it started to the checkout, with the new files included and without any external diff program or text conversion. It SHALL mask secrets in the whole diff with `mask_secrets` first, then cut it to `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS` characters. The `StepOutcome` SHALL hold the result as `diff`, and SHALL set `diff_cut` when it cut the diff. A done step SHALL report an empty diff.

#### Scenario: A stop after the agent wrote files
- **WHEN** the agent writes `src/sample.py` and a new test file, and the step stops on a failed verification command
- **THEN** the outcome holds a diff that names both files and holds their new lines, and the checkout is reset

#### Scenario: A long diff
- **WHEN** the discarded work is longer than `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS` characters
- **THEN** the diff of the outcome is exactly that long and `diff_cut` is true

#### Scenario: A secret in the diff
- **WHEN** the agent writes a line that holds a token in the form of a GitHub token and the step stops
- **THEN** the diff of the outcome holds the mask in place of the token

#### Scenario: A done step
- **WHEN** the step ends done
- **THEN** its diff is empty and `diff_cut` is false
