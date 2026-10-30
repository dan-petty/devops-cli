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
The exit checks SHALL run in this order: the own group keeps its tasks and no other group changed beyond its checkboxes, each verification command passes, the static checks pass, and every task of the group is ticked. The step SHALL stop at the first check that fails, name it as the reason, make no commit, and reset the checkout. A task left unticked after the first three checks first gets the extra turn of the requirement "A step asks once for the missing ticks".

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
- **WHEN** the model changes the text of a task of group 2 while it works on group 1
- **THEN** the step reports stopped, the reason names group 2, and the checkout is reset

#### Scenario: A task that the agent removes
- **WHEN** the model removes a task of group 1 from the `tasks.md` and ticks the others
- **THEN** the step reports stopped with the reason that the tasks of group 1 changed, and the checkout is reset

#### Scenario: A task that the agent moves
- **WHEN** the model swaps the texts of two tasks of group 1 and ticks them
- **THEN** the step reports stopped with the reason that the tasks of group 1 changed, and the checkout is reset

#### Scenario: A heading that the agent changes
- **WHEN** the model changes the heading of group 1
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
The shell tool of the agent SHALL run a command only when its first word is `git`, `uv`, `ruff` or `mypy`, and the command holds none of the operators that start a second command. Any other command SHALL come back to the model as a refusal, and the run SHALL go on. The refusal SHALL keep the text of the shell tool, cut to `CONST_ROADMAP_IMPLEMENT_ERROR_CHARS` characters, and SHALL add a hint. The shell SHALL run with `HOME` set to a temporary directory. The shell is no security boundary.

#### Scenario: A program outside the list
- **WHEN** the model calls the shell tool with `curl http://example.com`, and then ends its run
- **THEN** the call returns the refusal that `curl` is not in the allowed list followed by the list of the allowed programs, no process starts, and the run ends with the last message of the model

#### Scenario: The devops command
- **WHEN** the model calls the shell tool with `devops gh api -X POST repos/example/roadmap/issues`
- **THEN** the call returns the refusal that `devops` is not in the allowed list, and no process starts

#### Scenario: A second command
- **WHEN** the model calls the shell tool with `git status; curl http://example.com`
- **THEN** the call returns a refusal that names the operator and states the rule of one command in each call, and no process starts

#### Scenario: A habit of the table
- **WHEN** the model calls the shell tool with `python -m pytest`
- **THEN** the refusal holds "Instead of `python`: `uv run python`" and says that `python -m pip` is not to run, and no process starts

#### Scenario: A long word
- **WHEN** the model calls the shell tool with a first word of 5000 characters
- **THEN** the refusal holds the text of the shell cut to `CONST_ROADMAP_IMPLEMENT_ERROR_CHARS` characters, then the hint

#### Scenario: A file command
- **WHEN** the model calls the shell tool with `cat README.md`
- **THEN** the refusal names the tool `read_file`

#### Scenario: A change of directory
- **WHEN** the model calls the shell tool with `cd src`
- **THEN** the refusal says that `cd` is not needed because every command runs in the checkout

#### Scenario: The retry limit is unchanged
- **WHEN** the model calls the shell tool with `python -V` in every reply
- **THEN** the model got five refusals with a hint, and the sixth call ends the run as before

#### Scenario: The prompt and the table agree
- **WHEN** the table `IMPLEMENT_SHELL_REPLACEMENTS` or `IMPLEMENT_SHELL_PROGRAMS` differs from the prompt of the step, or a shell command of the prompt holds an operator that the shell refuses
- **THEN** a test fails

### Requirement: A run that reaches a limit ends stopped
`UsageLimits` SHALL cap a run, extra turn included, at `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` model requests and `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` tool calls. A run that reaches a limit, or breaks the rules of its tools past their retries, SHALL end as stopped, and the step SHALL reset the checkout. The reason SHALL hold the class and the message of the pydantic-ai error, masked and cut to `CONST_ROADMAP_IMPLEMENT_ERROR_CHARS` characters. The agent SHALL have no `delegate_task` tool.

#### Scenario: A model that never ends
- **WHEN** the model calls a tool in every reply
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: ` and holds the message of the error, the model got `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests at most, and the checkout is reset

#### Scenario: A model that calls too many tools
- **WHEN** the model calls more tools than `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` before it reaches the request limit
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `, and the checkout is reset

#### Scenario: The tools of the agent
- **WHEN** the step makes its first request
- **THEN** the function tools offered are `read_file`, `write_file`, `edit_file`, `list_files`, `grep` and `shell`

#### Scenario: The extra turn shares the budget
- **WHEN** the first turn used all but one of the model requests and the extra turn needs two
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `, and the model got `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests at most over both turns

#### Scenario: A model that keeps calling a refused program
- **WHEN** the model calls the shell tool with `pytest tests/test_sample.py` in every reply
- **THEN** the step reports stopped with a reason that starts with `UnexpectedModelBehavior: Tool 'shell' exceeded max retries count of 5.`, and the checkout is reset

#### Scenario: A secret in the message of the error
- **WHEN** the message of the pydantic-ai error holds a token in the form of a GitHub token
- **THEN** the reason holds the mask in place of the token

#### Scenario: A long message of the error
- **WHEN** the message of the pydantic-ai error is longer than `CONST_ROADMAP_IMPLEMENT_ERROR_CHARS` characters
- **THEN** the message in the reason is cut to that length, and the counts of the next requirement are still in the reason

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
When the agent ends its run, the check of the tasks passes, each verification command passes, the static checks pass, and a task of the group is unticked, the step SHALL run one more model turn. The turn SHALL continue the same conversation under the same `UsageLimits`. Its message SHALL name the path of the `tasks.md` and list the unticked tasks, and SHALL ask only for their ticks. The step SHALL run the turn at most once, and SHALL run none for a fix step.

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
The extra turn SHALL change no file except the `tasks.md` of the change. The step SHALL check this with git, by comparing the checkout after the turn with the tree of the checkout before it, and SHALL stop with a reason that names the other paths when the turn changed any. After the turn every exit check and the restore of the other groups SHALL run again. The outcome SHALL count the requests and the tokens of both turns, and the spend ledger SHALL hold the replies of both.

#### Scenario: The turn changes another file
- **WHEN** the model changes `src/sample.py` in the extra turn
- **THEN** the step reports stopped with the reason that names `src/sample.py`, makes no commit and resets the checkout

#### Scenario: The turn edits the text of another group
- **WHEN** the model changes the text of a task of group 2 in the extra turn
- **THEN** the step reports stopped, the reason names group 2, and the checkout is reset

#### Scenario: The turn ticks a task of another group
- **WHEN** the model ticks the tasks of group 1 and a task of group 2 in the extra turn
- **THEN** the step reports done, and the commit holds `tasks.md` with group 1 ticked and group 2 as it was

#### Scenario: The spend of two turns
- **WHEN** the first turn took two model requests and the extra turn took one
- **THEN** the outcome reports three requests, and the spend ledger holds the tokens of the three replies

### Requirement: A stopped step reports a masked diff of its discarded work
A step that ends as stopped SHALL read the diff of the work that it discards, from its start commit to the checkout, new files included, with no external diff program or text conversion. It SHALL mask secrets in the diff with `mask_secrets` first, then cut it to `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS` characters. The `StepOutcome` SHALL hold the result as `diff`, and SHALL set `diff_cut` when it cut the diff or the part that it masked. A done step SHALL report an empty diff.

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

### Requirement: The reason of the turn for the ticks names a bounded number of paths
When the turn for the ticks changes other files, the reason of the stop SHALL name at most `CONST_ROADMAP_IMPLEMENT_REASON_PATHS` paths in sorted order and SHALL give the count of the rest.

#### Scenario: The turn changes many files
- **WHEN** the model writes `CONST_ROADMAP_IMPLEMENT_REASON_PATHS` plus 30 new files in the extra turn
- **THEN** the reason names the first `CONST_ROADMAP_IMPLEMENT_REASON_PATHS` paths in order and ends with `and 30 more`

### Requirement: A stopped step reads a bounded diff that may hold bytes that are not UTF-8
A stopped step SHALL give `mask_secrets` at most `CONST_ROADMAP_IMPLEMENT_DIFF_READ_CHARS` characters of the diff, a multiple of `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS`, and SHALL set `diff_cut` when git printed more. It SHALL read the output of git with a replacement character for each byte that is not UTF-8, and SHALL raise no decode error.

#### Scenario: A very large diff
- **WHEN** the discarded work is longer than `CONST_ROADMAP_IMPLEMENT_DIFF_READ_CHARS` characters
- **THEN** `mask_secrets` gets at most that many characters, the diff of the outcome is cut to `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS` characters and `diff_cut` is true

#### Scenario: A file that is not UTF-8
- **WHEN** the discarded work holds a Latin-1 file
- **THEN** the step reports stopped with a diff that holds a replacement character in place of each byte that is not UTF-8, and raises no error

### Requirement: The reason of a stopped run counts the refused and the retried tool calls
A step that stops on a pydantic-ai error SHALL count the tool calls that a tool refused by its policy, by program, and the tool calls that came back as a retry for another cause. The reason SHALL end with both counts when a count is not zero. It SHALL list at most `CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS` programs, most refused first, and join the rest to `other`. A call counts as refused when it has a shell command and a `PermissionError` is in its `__cause__` chain.

#### Scenario: The call that exceeds the limit
- **WHEN** the model is refused more often than `CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES` times
- **THEN** the call that ends the run counts as refused too

#### Scenario: Refused commands
- **WHEN** the model calls the shell tool with `pytest tests/test_sample.py` in every reply, and the shell allows only `git`, `uv`, `ruff` and `mypy`
- **THEN** the reason ends with a new line and "Refused commands: pytest 6. Other retries: 0."

#### Scenario: Refused commands of two programs
- **WHEN** the model is refused `python` four times and `cd` twice, and then the run ends
- **THEN** the reason ends with "Refused commands: python 4, cd 2."

#### Scenario: Refused commands of many programs
- **WHEN** the model is refused more distinct programs than `CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS`
- **THEN** the reason lists that number of programs and the count of `other` holds the rest

#### Scenario: Arguments that fail validation
- **WHEN** the model calls the tool `read_file` without its `path` argument in every reply
- **THEN** the reason ends with "Refused commands: 0. Other retries: 6."

#### Scenario: A path outside the root
- **WHEN** the model calls `read_file` with the path `/etc/passwd` in every reply
- **THEN** the reason ends with "Refused commands: 0. Other retries: 6."

#### Scenario: A run with no retry
- **WHEN** the model calls `read_file` with a valid path in every reply until the request limit
- **THEN** the reason holds the message of the error and holds neither count

### Requirement: Every tool call of a step writes one line to the Job log
The agent of a step SHALL write one line to the standard error stream for each tool call. The line SHALL hold the name of the tool, the program of the `command` argument when the tool has one, and the outcome: `ok`, `refused`, `retry` or `failed`. The program SHALL be the first word of the command when it is a program of the allowlist or a program of `IMPLEMENT_SHELL_REPLACEMENTS`, else the word `other`. The line SHALL hold nothing else.

#### Scenario: A refused program
- **WHEN** the model calls the shell tool with `pytest tests/test_sample.py --secret-flag=abc`, and then ends its run
- **THEN** the standard error stream holds the line "Tool call: shell, program pytest, refused." and holds no text of the arguments

#### Scenario: A program of the allowlist
- **WHEN** the model calls a tool with the command `git status`
- **THEN** the line holds "program git"

#### Scenario: A call that returns
- **WHEN** the model calls `write_file` with a path and a content, and then ends its run
- **THEN** the standard error stream holds the line "Tool call: write_file, ok." and holds neither the path nor the content

#### Scenario: A call that fails validation
- **WHEN** the model calls `read_file` without its `path` argument
- **THEN** the standard error stream holds the line "Tool call: read_file, retry."

#### Scenario: A first word that is no program
- **WHEN** the first word of a shell command is an assignment such as `API_KEY=hunter2`, a path, a word with a space or a quote, an escape sequence, or the command has an unclosed quote
- **THEN** the line holds "program other" and holds no part of the word

#### Scenario: A short bare word that is no known program
- **WHEN** the first word of a shell command is a short bare word such as `hunter2password` that the model read from a file
- **THEN** the line and the reason of a stopped run hold "other" and not the word

#### Scenario: A refused path
- **WHEN** the model calls `read_file` with a path outside the root
- **THEN** the standard error stream holds the line "Tool call: read_file, retry."

#### Scenario: A call that the tool reports as failed
- **WHEN** a tool reports a failed call
- **THEN** the standard error stream holds the line "Tool call: <tool>, failed."

### Requirement: The table of a stopped step shows the reason as text
The table of `devops roadmap implement` SHALL print the reason and the last message as text. A bracket in either SHALL NOT be read as markup, and SHALL NOT raise an error.

#### Scenario: A reason with a closing tag
- **WHEN** the reason of a stopped step is "Tool x [/oops] failed"
- **THEN** the table holds that text

### Requirement: A step restores the checkboxes of the other groups
After each turn of the model, the step SHALL compare every group other than its own with its text before the run. A group that differs only in its checkboxes SHALL get the checkbox state of that text written back to `tasks.md`, and the step SHALL print one line to the error stream that names the restored groups. The commit SHALL hold the restored file.

#### Scenario: The model ticks a later group
- **WHEN** the model completes group 1, ticks its tasks and the tasks of group 2, which was unticked, and ends its run
- **THEN** the step reports done, the commit holds the work and `tasks.md` with group 1 ticked and group 2 unticked, and the step prints one line that names group 2

#### Scenario: The model unticks an earlier group
- **WHEN** the model works on group 2, ticks its tasks, and unticks a task of group 1, which was ticked
- **THEN** the step reports done, and the commit holds `tasks.md` with group 1 as it was

#### Scenario: A file with CRLF line ends
- **WHEN** the `tasks.md` has CRLF line ends and the model ticks a later group
- **THEN** the committed `tasks.md` keeps its CRLF line ends and the later group is unticked

#### Scenario: A file with lone CR line ends
- **WHEN** the model writes a `tasks.md` that has many lone CR line ends before the groups, and ticks a later group
- **THEN** the step reports done, and the committed `tasks.md` has the later group unticked on its own line

### Requirement: A change of another group beyond its checkboxes stops the step
After the restore, the text of each other group SHALL equal its text before the run. Any difference beyond the checkboxes SHALL stop the step with the group named: a title, a task, a command, a bullet or a line changed, added or removed. A group number that two groups hold after the run SHALL stop the step, and one that two groups hold before the run SHALL be refused before the step starts. The own group follows its own requirement. A fix step SHALL change no task and restore nothing.

#### Scenario: The model ticks a later group and edits its text
- **WHEN** the model ticks a task of group 2 and also changes the text of that task
- **THEN** the step reports stopped, the reason names group 2, and the checkout is reset

#### Scenario: The model changes a bullet of a later group
- **WHEN** the model ticks the tasks of group 2 and changes `-` to `*` before one of them
- **THEN** the step reports stopped, the reason names group 2, and the checkout is reset

#### Scenario: The model adds a line to a later group
- **WHEN** the model adds a paragraph to group 2, with or without a change of its checkboxes
- **THEN** the step reports stopped, the reason names group 2, and the checkout is reset

#### Scenario: A copy of a group hides an edit
- **WHEN** the model edits a task of group 2 and adds a second group 2 that is a copy of the original
- **THEN** the step reports stopped, the reason names group 2, and the checkout is reset

#### Scenario: A fix step with a copy of a group
- **WHEN** a fix step edits a task of group 2 and adds a second group 2 that is a copy of the original
- **THEN** the step reports stopped with the reason that a fix step changes no task

#### Scenario: A tasks file that numbers a group twice
- **WHEN** the `tasks.md` of the change holds two groups with the number 2
- **THEN** the step is refused before the model runs, and the message names the change and group 2

#### Scenario: A fix step
- **WHEN** a fix step ticks a task of any group
- **THEN** the step reports stopped with the reason that a fix step changes no task

### Requirement: A step writes the text of its own group back
After each turn of the model, the step SHALL write the raw lines of the region of its own group from before the run back to `tasks.md`, when the group keeps its tasks, their order and its heading. The region runs from the heading to the next numbered group. The step SHALL keep the checkboxes that the model set, print one line that names the group when the file changed, and run the verification commands of the text before the run. A fix step SHALL change no task.

#### Scenario: The model rewrites the text of a task
- **WHEN** the model writes its files, rewrites the text of task 1.1 in `tasks.md` to name another file, ticks the tasks of group 1, and ends its run
- **THEN** the step reports done, the commit holds `tasks.md` with the text of group 1 from before the run and its tasks ticked, and the step prints one line that names group 1

#### Scenario: The model rewrites the text in the extra turn
- **WHEN** the model leaves a task unticked, and in the extra turn rewrites the text of that task and ticks it
- **THEN** the step reports done, and the commit holds the text from before the run with the task ticked

#### Scenario: The model rewrites a verification command to one that passes
- **WHEN** the model replaces the command of a `Verification:` line of group 1 with a command that exits 0, and the original command exits 1
- **THEN** the step runs only the original command, reports stopped, the reason names the original command, and the checkout is reset

#### Scenario: The model rewrites a line that is no task
- **WHEN** the model changes a paragraph of group 1 that is no task, and ticks the tasks
- **THEN** the step reports done, and the commit holds the paragraph from before the run

#### Scenario: The model ticks and changes nothing else
- **WHEN** the model ticks the tasks of group 1 and changes no text
- **THEN** the step reports done, and the step prints no line about the group

#### Scenario: A file with CRLF line ends
- **WHEN** the `tasks.md` has CRLF line ends and the model rewrites the text of a task of group 1
- **THEN** the committed `tasks.md` keeps its CRLF line ends and the text from before the run

#### Scenario: A section that the model adds inside or after the group
- **WHEN** the model adds a `##` section with a ticked task inside group 1, or between group 1 and group 2, and ticks the tasks of group 1
- **THEN** the step reports done, and the commit holds the region of group 1 from before the run, with no added section and no repeated line

#### Scenario: A tick keeps the bytes of the group
- **WHEN** the last line of group 1 ends with two spaces and the model only ticks its tasks
- **THEN** the step reports done, the commit holds the two spaces, and the step prints no line about the group

#### Scenario: Mixed line ends
- **WHEN** the heading of group 1 ends with CRLF, its other lines end with LF, and the model rewrites a task and ticks the group
- **THEN** the committed group holds the CRLF heading and the LF lines of before the run

#### Scenario: A fix step edits a task
- **WHEN** a fix step edits the text of a task of group 1
- **THEN** the step reports stopped with the reason that a fix step changes no task
