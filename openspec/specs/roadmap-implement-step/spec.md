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
The exit checks SHALL run in this order: the agent made no commit, no test that existed at the start is lost, each verification command passes, the static checks pass, and every task of the group is ticked. The step SHALL stop at the first check that fails, name it as the reason, make no commit, and reset the checkout. A failed static check, and a task left unticked after the first four checks, first get the extra turn of their own requirements.

#### Scenario: A verification command fails
- **WHEN** the model ends its run with the files written and the tasks ticked, and the verification command exits 1
- **THEN** the step reports stopped, the reason names the command and its exit status, the checkout holds no new commit, and the written files are gone

#### Scenario: A static check fails
- **WHEN** the verification command exits 0 and `ruff check` exits 1 on the changed file, in the first turn and in the extra turn
- **THEN** the step reports stopped with the reason that `ruff check` failed, makes no commit and resets the checkout

#### Scenario: A task stays unticked
- **WHEN** the model ends its run and leaves a task of the group unticked, the verification command and the static checks exit 0, and the extra turn leaves the task unticked
- **THEN** the step reports stopped, the reason names the unticked task, and the checkout is reset

#### Scenario: A task stays unticked and a verification command fails
- **WHEN** the model ends its run and leaves a task of the group unticked, and the verification command exits 1
- **THEN** the step reports stopped with the reason that names the command and its exit status, the model gets no extra turn, and the checkout is reset

#### Scenario: The model changes another group
- **WHEN** the model changes the text of a task of group 2 while it works on group 1
- **THEN** the step reports done, and the commit holds group 2 as it was

#### Scenario: A task that the agent removes
- **WHEN** the model removes a task of group 1 from the `tasks.md` and ticks the others
- **THEN** the step ticks no task of group 1, gives the extra turn, and stops with the reason that names the first unticked task when the turn changes nothing

#### Scenario: A task that the agent moves
- **WHEN** the model swaps the texts of two tasks of group 1 and ticks them
- **THEN** the step reports done, and the commit holds the tasks in their order from before the run, ticked

#### Scenario: A heading that the agent changes
- **WHEN** the model changes the heading of group 1
- **THEN** the step reports done, and the commit holds the heading from before the run

#### Scenario: A tasks file that is gone
- **WHEN** the model removes the `tasks.md` of the change
- **THEN** the step writes the file from before the run, gives the extra turn for the unticked tasks, and stops with the reason that names the first unticked task when the turn changes nothing

#### Scenario: A verification command outside the allowlist
- **WHEN** a Verification line of the group names `curl http://example.com`
- **THEN** the step reports stopped, the reason names `curl` as not allowed, the command does not run, and the checkout is reset

#### Scenario: A test that the agent removes
- **WHEN** the model replaces a test file with a file that holds fewer of its tests, and ticks the tasks
- **THEN** the step reports stopped with the reason that names the file and the missing tests, no verification command runs, and the checkout is reset

### Requirement: A step makes the only commit
The first exit check SHALL be that `HEAD` is still the commit where the step started.

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
The shell tool of the agent SHALL run a command only when its first word is `git`, `uv`, `ruff` or `mypy`, and the command holds none of the operators that start a second command. Any other command SHALL come back to the model as a refusal, and the run SHALL go on. The refusal SHALL keep the text of the shell tool, cut to `CONST_ROADMAP_RUN_ERROR_CHARS` characters, and SHALL add a hint. The shell SHALL run with `HOME` set to a temporary directory. The shell is no security boundary.

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
- **THEN** the refusal holds the text of the shell cut to `CONST_ROADMAP_RUN_ERROR_CHARS` characters, then the hint

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
`UsageLimits` SHALL cap a run, extra turn included, at `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests and `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` tool calls. A run that reaches a limit, or breaks its tools' rules past their retries, SHALL end as stopped, and the step SHALL reset the checkout. The reason SHALL hold the class and the `message` of the pydantic-ai error, masked and cut to `CONST_ROADMAP_RUN_ERROR_CHARS` characters, never its `body`. The agent SHALL have no `delegate_task` tool.

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
- **WHEN** the message of the pydantic-ai error is longer than `CONST_ROADMAP_RUN_ERROR_CHARS` characters
- **THEN** the message in the reason is cut to that length, and the counts of the next requirement are still in the reason

#### Scenario: The body of the error
- **WHEN** the pydantic-ai error has the message `The reply broke the rules.` and the body `MODEL-TEXT`
- **THEN** the reason is `UnexpectedModelBehavior: The reply broke the rules.`, with no `MODEL-TEXT`

### Requirement: The step writes nothing to GitHub and a dry run makes no request
The step SHALL read the item once and SHALL write no issue, comment, label or milestone. With `--dry-run` it SHALL make no request of any kind, SHALL start no model run, SHALL change nothing in the checkout, and SHALL return a `StepOutcome` marked as a dry run that lists the requests a run makes.

#### Scenario: A dry run
- **WHEN** `devops roadmap implement --item 7 --group 1 --dry-run` runs
- **THEN** the command exits 0, it prints the read of issue 7 and the model requests, the model gets no request, and the roadmap store sees no read

### Requirement: The outcome is a structured report
The step SHALL return a `StepOutcome` with the status (done or stopped), the reason, the last message of the agent, the commit, and the requests, the tool calls and the tokens that the run spent. The command SHALL print it as a table, or as JSON with `--format json`, and SHALL exit 1 when the status is stopped. The step SHALL record the spend of the run as one record of the spend ledger.

#### Scenario: A stopped step as JSON
- **WHEN** a step stops on a failed verification and the command runs with `--format json`
- **THEN** the output is one JSON object with `status` `stopped`, the reason, an empty `commit`, and the counts of requests, tool calls and tokens, and the exit code is 1

#### Scenario: The spend record
- **WHEN** a step ends after two model requests
- **THEN** the spend ledger holds one record for the run with the sum of the tokens of the two replies

#### Scenario: The tool calls
- **WHEN** a step ends after three tool calls in two replies
- **THEN** the outcome holds `tool_calls` 3

### Requirement: A fix step makes a failed check pass
The step SHALL accept a fix request: the name of a failed check and its log. The group of a fix step SHALL be "Make check `<name>` pass", with the verification commands of every group of the change. The inputs SHALL hold the log cut to `CONST_ROADMAP_IMPLEMENT_LOG_CHARS` characters from its end. The exit checks SHALL be those of a group, except that no task is ticked and `tasks.md` SHALL be as it was. A done fix step SHALL commit as `Make check <name> pass (#N)`.

#### Scenario: A fix step with a long log
- **WHEN** a fix request holds a log longer than the limit
- **THEN** the first message of the step holds the last characters of the log up to the limit, and the first characters are not in it

#### Scenario: The fix step ticks a task
- **WHEN** the model of a fix step ticks or edits a task in `tasks.md`, and changes a source file
- **THEN** the step reports done, and the commit holds the source file and `tasks.md` as it was

### Requirement: A step asks once for the missing ticks
When the agent ends its run, the check of the tasks passes, each verification command passes, the static checks pass, and a task of the group is unticked, the step SHALL run one more model turn. The turn SHALL continue the same conversation under the same `UsageLimits`. Its message SHALL name the path of the `tasks.md` and list the unticked tasks, and SHALL ask only for their ticks. A step SHALL get one extra turn at most, whichever check asks for it, and none for the ticks of a fix step.

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
The extra turn SHALL change no file except the `tasks.md` of the change. The step SHALL check this with git, by comparing the checkout after the turn with the tree of the checkout before it, and SHALL stop with a reason that names the other paths when the turn changed any. After the turn every exit check and the restore of `tasks.md` SHALL run again. The outcome SHALL count the requests and the tokens of both turns, and the spend ledger SHALL hold the replies of both.

#### Scenario: The turn changes another file
- **WHEN** the model changes `src/sample.py` in the extra turn
- **THEN** the step reports stopped with the reason that names `src/sample.py`, makes no commit and resets the checkout

#### Scenario: The turn edits the text of another group
- **WHEN** the model changes the text of a task of group 2 in the extra turn
- **THEN** the step reports done, and the commit holds group 2 as it was

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
The agent of a step SHALL write one line to the standard error stream for each tool call, when it ends. The line SHALL hold the name of the tool, the program of the `command` argument when the tool has one, and the outcome: `ok`, `refused`, `retry` or `failed`. The program SHALL be the first word of the command when it is a program of the allowlist or of `IMPLEMENT_SHELL_REPLACEMENTS`, else `other`. The line SHALL hold nothing else but the reason of a retry.

#### Scenario: A program of the allowlist
- **WHEN** the model calls a tool with the command `git status`
- **THEN** the line holds "program git"

#### Scenario: A call that returns
- **WHEN** the model calls `write_file` with a path and a content, and then ends its run
- **THEN** the standard error stream holds the line "Tool call: write_file, ok." and holds neither the path nor the content

#### Scenario: A call that fails validation
- **WHEN** the model calls `read_file` without its `path` argument
- **THEN** the standard error stream holds the line "Tool call: read_file, retry."

#### Scenario: A short bare word that is no known program
- **WHEN** the first word of a shell command is a short bare word such as `hunter2password` that the model read from a file
- **THEN** the line and the reason of a stopped run hold "other" and not the word

#### Scenario: A refused path
- **WHEN** the model calls `read_file` with a path outside the root
- **THEN** the standard error stream holds the line "Tool call: read_file, retry." and no part of the path

#### Scenario: A call that the tool reports as failed
- **WHEN** a tool reports a failed call
- **THEN** the standard error stream holds the line "Tool call: <tool>, failed."

### Requirement: A call with a command writes the command to the Job log before it runs
Before a call that has a `command` runs, the agent SHALL write the line `Tool call: <tool>, started: <command>`. The command SHALL be the first word and at most `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS` words, escaped and cut to `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS` characters. The line SHALL hide each secret, the value of each `name=value` word that is not a number, and each word with a space. When the first word is no known program, the command SHALL be `other`.

#### Scenario: A refused program
- **WHEN** the model calls the shell tool with `pytest tests/test_sample.py`, and then ends its run
- **THEN** the standard error stream holds the lines "Tool call: shell, started: pytest tests/test_sample.py" and "Tool call: shell, program pytest, refused."

#### Scenario: The line comes before the call
- **WHEN** the model calls the shell tool with `uv run pytest -n 48`, and the tool is still running
- **THEN** the standard error stream holds the line "Tool call: shell, started: uv run pytest -n 48" and no line with an outcome

#### Scenario: A long command
- **WHEN** the command has more words than `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS`, or more characters than `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS`
- **THEN** the line holds the first words, cut, and ends with " ..."

#### Scenario: A secret in an argument
- **WHEN** the command is `git remote add origin https://user:ghp_<token>@example.com/x.git`, with a GitHub token in place of `<token>`
- **THEN** the line holds no part of the token

#### Scenario: A value after a name
- **WHEN** an argument has the form `name=value` and the value is not a number, for example `ai.api_key=<value>` or `http.extraheader=AUTHORIZATION: basic <value>`
- **THEN** the line holds the name and the word `<masked>` in place of the value, and an argument with a number as the value, such as `--numprocesses=48`, stays as it is

#### Scenario: Free text in an argument
- **WHEN** an argument holds a space, as the message of a commit does
- **THEN** the line holds the word `<masked>` in place of the argument

#### Scenario: A control character in an argument
- **WHEN** an argument holds an escape sequence or another control character that is no space
- **THEN** the line is one line, and it holds the escaped form of the character

#### Scenario: A first word that is no program
- **WHEN** the first word of a shell command is an assignment such as `API_KEY=hunter2`, a path, a word with a space or a quote, an escape sequence, or the command has an unclosed quote
- **THEN** the lines hold "started: other" and "program other" and hold no part of the command

### Requirement: The table of a stopped step shows the reason as text
The table of `devops roadmap implement` SHALL print the reason and the last message as text. A bracket in either SHALL NOT be read as markup, and SHALL NOT raise an error.

#### Scenario: A reason with a closing tag
- **WHEN** the reason of a stopped step is "Tool x [/oops] failed"
- **THEN** the table holds that text

### Requirement: A failed model call ends the step stopped
A run that ends on a failed model call (a `ModelAPIError` that is not a refused key) SHALL end as stopped, and the step SHALL reset the checkout. The outcome of a failed turn SHALL hold the requests and the tokens that the turn spent, the failed request included, and the last text of the model, added to those of the turn before it.

#### Scenario: A model call fails in the first turn
- **WHEN** the agent writes `src/sample.py` and a new test file, and its next model call raises a `ModelAPIError`, a `ModelHTTPError` with the status 503, or a `ModelRequestTimeout`
- **THEN** the step reports stopped with a reason that starts with the class of the error, the outcome holds the masked diff of both files, the requests (the reply and the failed request) and the tokens, and the last text of the model, and the checkout is reset

#### Scenario: A model call fails in the extra turn
- **WHEN** the first turn passes every check and leaves a task unticked, and the model call of the extra turn for the ticks raises one of those errors
- **THEN** the step reports stopped with a reason that starts with the class of the error, the outcome holds the masked diff of the work of the first turn, the requests of both turns, and the last text of the first turn, and the checkout is reset

### Requirement: A failed model call gives a reason with the error text of the provider
The reason of a step that a failed model call ended SHALL hold the class of the error, the HTTP status if any, and the name of the model. For a `ModelHTTPError` it SHALL also hold the first line of the error text of the body: masked, cut like other stop text, without quoted parts, and ending at the first `=` or `;`. A gateway dict `{'error': '<text>'}` ending that line is read as `<text>`. For a `ModelRequestTimeout` it SHALL hold the deadline in seconds. It SHALL hold no other value.

#### Scenario: The body of a 400
- **WHEN** the body of a `ModelHTTPError` with the status 400 is a dict with the `message` "XML syntax error on line 75: unexpected EOF"
- **THEN** the reason is "ModelHTTPError: HTTP 400, model example-model, body: XML syntax error on line 75: unexpected EOF"

#### Scenario: The gateway wrapper
- **WHEN** the message of the body is "litellm.BadRequestError: Ollama_chatException - KeyError: 'message', Got unexpected response from Ollama: {'error': 'XML syntax error on line 70: unexpected EOF'}"
- **THEN** the reason holds "XML syntax error on line 70: unexpected EOF"

#### Scenario: A token in the gateway wrapper
- **WHEN** the error text inside the gateway wrapper holds a token in the form of a GitHub token
- **THEN** the reason holds the text with the token masked

#### Scenario: A quoted secret
- **WHEN** the error text of the body, with or without the wrapper, holds a quoted part such as "db_password: hunter2" that has no `=` and no known secret form
- **THEN** the reason holds `<text>` in place of the quoted part

#### Scenario: A message and a body of a failed model call
- **WHEN** the message of a `ModelAPIError` holds a token in the form of a GitHub token, or the body of a `ModelHTTPError` is a dict with the values of the keys `x-api-key` and `api_key` and no error text
- **THEN** the reason holds neither the token nor the values, and it is the class, the status when there is one, and the name of the model

#### Scenario: A token in the body
- **WHEN** the error text of the body holds a token in the form of a GitHub token, or is longer than the limit of stop text
- **THEN** the reason holds the text with the token masked, cut to the limit

#### Scenario: A body that echoes the model
- **WHEN** the error text of the body is "error parsing tool call: raw='{...DB_PASSWORD=hunter2...}', err=EOF", or holds a key and value such as "api_key=abc", or an unclosed quote, or a second line
- **THEN** the reason holds the first line up to the first `=` or `;`, with each quoted part hidden, and no value of the echo

#### Scenario: The diff cannot be read
- **WHEN** a model call fails and `git add` or `git diff` fails when the step reads the diff of the discarded work
- **THEN** the step reports stopped with an empty diff, the reason starts with the class of the error and holds the text of the git error after it, and the checkout is reset

#### Scenario: The deadline
- **WHEN** a model call raises a `ModelRequestTimeout` for a deadline of 600 seconds
- **THEN** the reason is "ModelRequestTimeout: model example-model, no complete reply in 600 seconds"

### Requirement: A refused key stops the whole run
A model call that fails with a `ModelHTTPError` of the status 401 or 403 SHALL raise `AICredentialsError` out of the step after the checkout is reset, and the job SHALL NOT run the next item.

#### Scenario: A refused key in the first turn
- **WHEN** the model call raises a `ModelHTTPError` with the status 401
- **THEN** `run_step` raises `AICredentialsError` and the checkout is reset

#### Scenario: A refused key in the extra turn
- **WHEN** the first turn passes every check, and the model call of the extra turn raises a `ModelHTTPError` with the status 401 or 403
- **THEN** `run_step` raises `AICredentialsError` and the checkout is reset

#### Scenario: A refused key in a job
- **WHEN** the model call of the first step of an item raises a `ModelHTTPError` with the status 401
- **THEN** `apply_implement` raises `AICredentialsError`, and the item gets no stop comment

### Requirement: A step writes tasks.md back to its text before the run
After each turn of the model, the step SHALL write the `tasks.md` of the change as it was before the run, with each task of its own group ticked that the model ticked, by position. The step SHALL tick none when the model changed the number of the tasks of the group. The step SHALL print one line that names the change when the file differed, and SHALL stop for no edit of the file. A fix step SHALL tick none. A file that numbers a group twice SHALL be refused before the step starts.

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
- **WHEN** the model leaves a task unticked, and in the extra turn rewrites the text of that task and ticks it
- **THEN** the step reports done, and the commit holds the text from before the run with the task ticked

#### Scenario: The model rewrites a verification command to one that passes
- **WHEN** the model replaces the command of a `Verification:` line of group 1 with a command that exits 0, and the original command exits 1
- **THEN** the step runs only the original command, reports stopped, the reason names the original command, and the checkout is reset

#### Scenario: The model adds, removes or reorders groups or tasks
- **WHEN** the model adds a group, removes a group, swaps two tasks of group 2, or adds a section outside every group, and ticks the tasks of group 1
- **THEN** the step reports done, and the commit holds the structure from before the run with group 1 ticked

#### Scenario: The model ticks part of the group
- **WHEN** the model ticks one of the two tasks of group 1
- **THEN** the step gives the extra turn for the other task, and the task stays unticked in the file

#### Scenario: The model changes the number of the tasks of its group
- **WHEN** the model adds a task to group 1 and ticks every task of the group
- **THEN** the step ticks none, gives the extra turn, and stops with the first unticked task named when the turn changes nothing

#### Scenario: The model removes or garbles the file
- **WHEN** the model removes `tasks.md`, or writes bytes that are not UTF-8 to it, and ticks nothing else
- **THEN** the step writes the file from before the run, and the unticked tasks of the group give the extra turn

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

### Requirement: The job formats the changed Python files
Before the verification commands and the static checks, the step SHALL run `uv run ruff format` on the changed Python files, outside the shell of the agent, and stage the files it changed. The step SHALL print one line that names them. A formatter that fails SHALL stop the step. `ruff check` SHALL not fix. The step SHALL pass the file names after `--`, and SHALL stop on a symbolic link before it runs a tool.

#### Scenario: Correct code that is unformatted
- **WHEN** the model writes correct code that the formatter would change, ticks the tasks, and ends its run
- **THEN** the step reports done, the commit holds the formatted file, and the step prints one line that names the file

#### Scenario: Code that is formatted
- **WHEN** the formatter changes no file
- **THEN** the step prints no line about the format and reports done

#### Scenario: A lint or type error
- **WHEN** the code is unformatted and `ruff check` exits 1 after the format run
- **THEN** the step reports stopped with the reason that `ruff check` failed

#### Scenario: A file with a syntax error
- **WHEN** the formatter exits with status 2 on a changed file
- **THEN** the step reports stopped, the reason names the format command and its exit status, and the checkout is reset

#### Scenario: Only the changed files
- **WHEN** the model changes one Python file and one document
- **THEN** the format command names the Python file only

#### Scenario: A file named like an option
- **WHEN** a changed file has a name that starts with `-`
- **THEN** each tool gets the name after `--`, so the tool reads it as a path

#### Scenario: A symbolic link
- **WHEN** a changed Python file is a symbolic link
- **THEN** the step reports stopped, the reason names the link, and no formatter runs

### Requirement: A failure of the generation inside a stream names a known cause
When a model call fails with a `ModelHTTPError` of the status 400 inside an open stream that is no context window error, the reason of the stopped step SHALL hold one more line, after the line of the class, the status and the body. The line SHALL say that the provider failed inside the stream and that tool call parsing failed is a known cause. The step SHALL choose the line by the fields of the error and not by its text.

#### Scenario: A failure inside a stream
- **WHEN** a model call fails with a 400 inside an open stream, and every send fails
- **THEN** the reason holds a line that says tool call parsing failed is a known cause, after the line of the class, the status and the body

#### Scenario: A failure outside a stream
- **WHEN** a model call fails with a 400 that is not inside a stream, or with a 503
- **THEN** the reason holds no such line

### Requirement: An error of the generation inside a stream is sent again
When a model call fails with a `ModelHTTPError` of the status 400 inside an open stream that is no context window error, the step SHALL send the request again with the same history, at most `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS` times in a row. A send that gets a reply SHALL give the next failed request its own resends. The limits SHALL count the failed requests too. After the last send, the step SHALL stop with the reason of a failed model call.

#### Scenario: Two separate failures
- **WHEN** a model request fails with a 400 inside a stream, a good reply follows, a later request fails the same way, and the next send answers with a good reply
- **THEN** each failed request is sent again, and the step ends done

#### Scenario: One failed send
- **WHEN** the first model request fails with a 400 inside a stream, and the second request answers with a good reply that ends the run
- **THEN** the step ends done, and the second request holds the same messages as the first

#### Scenario: Every send fails
- **WHEN** every model request fails with a 400 inside a stream with the body "XML syntax error on line 75: unexpected EOF"
- **THEN** the step stops, the reason holds the body, and the model got `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS` plus one requests

#### Scenario: Other failed model calls
- **WHEN** a model request fails with a 400 that is not inside a stream, a 503, or a 400 that is a context window error
- **THEN** the model gets no second request, and the step stops

#### Scenario: The failed send counts in the limit
- **WHEN** the replies and the failed send reach `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS`
- **THEN** the model gets no more than that many requests, and the step stops with the reason of the request limit

#### Scenario: A failure in the extra turn
- **WHEN** the model request of the extra turn for the ticks fails once with a 400 inside a stream
- **THEN** the request is sent again, and the extra turn ends with the ticks

### Requirement: A step asks once for a fix of a failed static check
When the agent ends its run, each verification command passes, and `ruff check` or `mypy --strict` fails, the step SHALL run one more turn in the same conversation under the same `UsageLimits`. Its message SHALL hold the text of the failure and the unticked tasks, if any. The step SHALL mask secrets in the text with `mask_secrets` first, then cut it to `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters. The step SHALL run the turn at most once. Every exit check SHALL run again after it.

#### Scenario: An unused import
- **WHEN** the model ticks the tasks and ends its run, `ruff check` exits 1 for an unused import in a changed file, and the model removes the import in the extra turn
- **THEN** the step reports done, the extra turn got the text of the failure, the commit holds the file without the import, and `ruff check` ran twice

#### Scenario: The failure stays
- **WHEN** `ruff check` still exits 1 after the extra turn
- **THEN** the step reports stopped with the reason that names `ruff check` and its exit status, the model got no third turn, and the checkout is reset

#### Scenario: A failed type check
- **WHEN** `mypy --strict` exits 1 after the first turn, and the model fixes the file in the extra turn
- **THEN** the step reports done, and the extra turn got the text of the failure of `mypy`

#### Scenario: A failure and an unticked task
- **WHEN** `ruff check` exits 1 after the first turn, and a task of the group is unticked
- **THEN** the message of the extra turn holds the text of the failure and the unticked task, and the model gets one extra turn

#### Scenario: The ticks stay missing
- **WHEN** the extra turn fixes the static failure and leaves a task unticked
- **THEN** the step reports stopped with the reason that names the unticked task, and the model gets no third turn

#### Scenario: A failed verification command
- **WHEN** a verification command exits 1
- **THEN** the model gets no extra turn for it

#### Scenario: A failure after the turn for the ticks
- **WHEN** the extra turn for the ticks ends and `ruff check` exits 1
- **THEN** the step reports stopped with the reason that names `ruff check`, and the model gets no second extra turn

#### Scenario: A fix step
- **WHEN** a fix step ends with a changed file and `ruff check` exits 1
- **THEN** the model gets one extra turn that holds the text of the failure and no list of ticks

#### Scenario: The extra turn shares the budget
- **WHEN** the first turn used all but one of the model requests and the extra turn needs two
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `

### Requirement: The turn for a failed static check changes only the files of the step
The turn for a failed static check SHALL change no file except `tasks.md` and the files that the step had changed before the turn. The step SHALL check this with git, and SHALL stop with a reason that names the other paths when the turn changed any.

#### Scenario: The turn changes a file that the step did not change
- **WHEN** the model changes `src/other.py` in the extra turn, and the step had not changed it
- **THEN** the step reports stopped with the reason that names `src/other.py`, makes no commit and resets the checkout

#### Scenario: The turn changes a file that the step changed
- **WHEN** the model changes `src/sample.py` in the extra turn, and the step had changed it
- **THEN** the step checks all exit checks again and does not stop for the change

### Requirement: The shell of a step takes the worker bound of the process
The shell of a step SHALL get `PYTEST_XDIST_AUTO_NUM_WORKERS` with the value of the process when the process has it, and SHALL not set it otherwise.

#### Scenario: The process has the variable
- **WHEN** the process sets `PYTEST_XDIST_AUTO_NUM_WORKERS` to `2`
- **THEN** the environment of the shell holds the same value

#### Scenario: The process has no variable
- **WHEN** the process does not set it
- **THEN** the environment of the shell does not hold it

### Requirement: A step keeps the tests that existed
Every test that a `.py` file under `tests/` held at the commit where the step started SHALL be in the checkout after the run, by qualified name (`test_x` or `Class.test_x`). A test is a function named `test_*`. When a test is lost, the step SHALL stop with a reason that names the file and at most `CONST_ROADMAP_IMPLEMENT_REASON_TESTS` of its tests, and SHALL give no extra turn. A file that does not parse is skipped.

#### Scenario: A test file that the agent replaces
- **WHEN** a test file holds `test_a` and `test_b` at the start, and the model writes a file that holds `test_c`
- **THEN** the step reports stopped, the reason names the file, `test_a` and `test_b`, and the checkout is reset

#### Scenario: A test that the agent adds
- **WHEN** the model adds `test_c` to a test file that holds `test_a` and `test_b`
- **THEN** the step reports done

#### Scenario: A test that the agent renames
- **WHEN** the model renames `test_a` to `test_z` in its file
- **THEN** the step reports stopped, and the reason names `test_a`

#### Scenario: A test file that the agent deletes
- **WHEN** the model deletes a test file that holds `test_a`
- **THEN** the step reports stopped, and the reason names the file and `test_a`

#### Scenario: A test that the agent moves
- **WHEN** the model moves `Check.test_a` from one test file to a new test file
- **THEN** the step reports stopped, and the reason names the old file and `Check.test_a`

#### Scenario: A test that loses its body
- **WHEN** the model keeps the name of `test_a` and replaces its body with `pass`
- **THEN** this check does not stop the step: it reads names only

#### Scenario: A file that does not parse
- **WHEN** a test file has a syntax error after the run, or at the start
- **THEN** this check does not stop the step, and the static check judges the file

#### Scenario: A long list of lost tests
- **WHEN** the model drops more than `CONST_ROADMAP_IMPLEMENT_REASON_TESTS` tests of a file
- **THEN** the reason names that many tests in order and gives the count of the rest

### Requirement: A retried tool call writes the reason that the tool returned
After `retry`, the line of a call SHALL hold the message of the `ModelRetry` that the tool raised, in brackets, masked, escaped to one line and cut to `CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS` characters. When the message lacks the `path` argument of the call, the line SHALL add "Path: <path>" after it. A retry that is a refusal by policy, and a retry of a failed validation, SHALL have no reason.

#### Scenario: An edit whose old text is missing
- **WHEN** the model calls `edit_file` with an `old_text` that the file does not hold
- **THEN** the line is "Tool call: edit_file, retry (old_text not found in <path>. No changes were written.)." and holds no part of `old_text`

#### Scenario: A retry whose message has no path
- **WHEN** the model calls `edit_file` with a `path` and with neither `old_text` nor `replacements`
- **THEN** the reason in the line ends with "Path: <path>"

#### Scenario: A secret in a reason
- **WHEN** the message of a retry holds a GitHub token
- **THEN** the line holds no part of the token

#### Scenario: A long reason
- **WHEN** the message of a retry is longer than `CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS`
- **THEN** the reason in the line is cut to that length and ends with " ..."

#### Scenario: A line break in a reason
- **WHEN** the message of a retry holds a line break or an escape sequence
- **THEN** the line is one line, and it holds the escaped form

#### Scenario: A retry with no reason
- **WHEN** a tool refuses a path outside the root, or the model calls a tool with arguments that fail validation
- **THEN** the line holds no reason

### Requirement: The reason of a retried call shows only a path of the checkout
The line of a retried call SHALL show the `path` argument of the call only when it names a file or a directory of the checkout, and SHALL show "<path>" in its place otherwise. The cut of a long message SHALL leave room for "Path: <path>".

#### Scenario: A long reason without the path
- **WHEN** the message of a retry is longer than `CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS` and lacks the `path` argument
- **THEN** the reason in the line is cut and ends with "Path: <path>"

#### Scenario: A path that is no file of the checkout
- **WHEN** the `path` argument is a plain string that no file of the checkout has, and the message names it
- **THEN** the line shows "<path>" in its place and holds no part of the string

### Requirement: The reason of a stopped run names the last retries of the tool that ended it
When a tool exceeds its retries, the reason of the stopped run SHALL end with a line that names the tool and its last `CONST_ROADMAP_IMPLEMENT_STOP_REASONS` reasons, in the form of the Job log. A run that ends on another cause SHALL have no such line.

#### Scenario: A tool that ends the run on retries
- **WHEN** the model calls `edit_file` with an `old_text` that the file does not hold in every reply
- **THEN** the reason ends with a line "Last retries of edit_file: " and the last reasons of that tool, and it holds no part of `old_text`

#### Scenario: A secret in the last reasons
- **WHEN** the message of the last retries holds a GitHub token
- **THEN** the reason holds no part of the token

#### Scenario: Retries with no reason
- **WHEN** the model calls `read_file` without its `path` argument in every reply
- **THEN** the reason holds no line of reasons

#### Scenario: A run that ends on a limit
- **WHEN** the run ends on the request limit after retries of `edit_file`
- **THEN** the reason holds no line of reasons

### Requirement: A model reply has an output cap and a call has a deadline
The agent of a step SHALL set the model settings `max_tokens` to `CONST_ROADMAP_IMPLEMENT_MAX_OUTPUT_TOKENS` and `request_timeout` to `CONST_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS`. The deadline SHALL be less than the timeout of the router in `k8s/llm/gateway/config.yaml`. A call that runs past the deadline SHALL end the step as stopped, and the model SHALL get no second request for it.

#### Scenario: The settings of the first request
- **WHEN** the step makes its first model request
- **THEN** the model settings of the request hold the cap and the deadline

#### Scenario: The cap reaches the wire
- **WHEN** the agent of a step sends a request to an OpenAI chat model
- **THEN** the body of the request holds `max_completion_tokens` with the value of the cap, and no `request_timeout`

#### Scenario: The deadline is short of the router timeout
- **WHEN** a test reads `router_settings.timeout` of the gateway config
- **THEN** the deadline is less than that timeout

#### Scenario: A call that never ends
- **WHEN** a model call does not answer within the deadline
- **THEN** the step reports stopped with a reason that starts with `ModelRequestTimeout: ` and holds the deadline, the model got one request, and the checkout is reset

### Requirement: A reply that reaches the output cap stops the step with its cause
A model reply with the finish reason `length` SHALL end the run at once, without a further request or tool call. The step SHALL end as stopped, and SHALL reset the checkout. The reason SHALL start with `OutputCapReached: ` and SHALL hold the cap. The request SHALL count in the requests and the spend of the step, and the step SHALL not send it again. A reply of a size under the cap SHALL pass.

#### Scenario: A reply that the cap ends
- **WHEN** the model answers with a text and the finish reason `length`
- **THEN** the step reports stopped with a reason that holds the cap as a number, the model got one request, the outcome counts one request, and the checkout is reset

#### Scenario: A tool call that the cap cuts
- **WHEN** the model answers with a `write_file` call whose arguments are not whole and the finish reason `length`
- **THEN** the step reports stopped with the same reason, the model got one request, the tool did not run, and the checkout is reset

#### Scenario: The counts stay in the reason
- **WHEN** the shell tool refused one command, and a later reply has the finish reason `length`
- **THEN** the reason holds the cap, and then the count of the refused commands

#### Scenario: A reply under the cap
- **WHEN** the model answers with a `write_file` call of three quarters of the cap and the finish reason `tool_calls`, and then ends the run
- **THEN** the step ends done
