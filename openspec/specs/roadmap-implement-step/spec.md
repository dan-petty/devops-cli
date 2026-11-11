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
The exit checks SHALL run in this order: the agent made no commit, no test from the start is lost, each verification command passes, the static checks pass, and the hooks pass. Then the job ticks the group, as the requirement of the job ticks says. The step SHALL stop at the first check that fails, name it as the reason, make no step commit, and reset the checkout to its last `wip:` commit, or to its start. A failed static check or hook first gets the extra turns of its own requirement.

#### Scenario: A verification command fails
- **WHEN** the model ends its run with the files written and the tasks ticked, and the verification command exits 1
- **THEN** the step reports stopped, the reason names the command and its exit status, the checkout holds no new commit, and the written files are gone

#### Scenario: A static check fails
- **WHEN** the verification command exits 0 and `ruff check` exits 1 on the changed file, in the first turn and in every extra turn
- **THEN** the step reports stopped with the reason that `ruff check` failed, makes no step commit and resets the checkout to its last `wip:` commit

#### Scenario: A task stays unticked
- **WHEN** the model ends its run and leaves a task of the group unticked, and an exit check of the group fails
- **THEN** the job writes no tick, the step reports stopped, and the checkout is reset

#### Scenario: A task stays unticked and a verification command fails
- **WHEN** the model ends its run and leaves a task of the group unticked, and the verification command exits 1
- **THEN** the step reports stopped with the reason that names the command and its exit status, the model gets no extra turn, and the checkout is reset

#### Scenario: The model changes another group
- **WHEN** the model changes the text of a task of group 2 while it works on group 1
- **THEN** the step reports done, and the commit holds group 2 as it was

#### Scenario: A task that the agent removes
- **WHEN** the model removes a task of group 1 from the `tasks.md` and ticks the others
- **THEN** the step restores the tasks of group 1 as they were before the run, and the job ticks them when the exit checks pass

#### Scenario: A task that the agent moves
- **WHEN** the model swaps the texts of two tasks of group 1 and ticks them
- **THEN** the step reports done, and the commit holds the tasks in their order from before the run, ticked

#### Scenario: A heading that the agent changes
- **WHEN** the model changes the heading of group 1
- **THEN** the step reports done, and the commit holds the heading from before the run

#### Scenario: A tasks file that is gone
- **WHEN** the model removes the `tasks.md` of the change
- **THEN** the step writes the file from before the run, and the job ticks the group when the exit checks pass

#### Scenario: A verification command outside the allowlist
- **WHEN** a Verification line of the group names `curl http://example.com`
- **THEN** the step reports stopped, the reason names `curl` as not allowed, the command does not run, and the checkout is reset

#### Scenario: A test that the agent removes
- **WHEN** the model replaces a test file with a file that holds fewer of its tests, and ticks the tasks
- **THEN** the step reports stopped with the reason that names the file and the missing tests, no verification command runs, and the checkout is reset

### Requirement: A step makes the only commit
The first exit check SHALL put `HEAD` back at the commit where the step started, or at the last `wip:` commit of the step, with `git reset --soft` when the agent moved it, so the checkout keeps the work of the agent and the later exit checks judge that work. The step SHALL stop with the class `head_moved` only when the reset exits with a status other than 0.

#### Scenario: A commit by the agent
- **WHEN** the agent commits its work with `git`, and ticks the tasks
- **THEN** the step resets `HEAD` to the commit where it started, prints one muted line that names the moved head and the expected head, and reports done with one commit whose parent is the commit where the step started and that holds the work of the agent

#### Scenario: A commit by the agent after a `wip:` commit
- **WHEN** the step made a `wip:` commit and the agent then makes its own commit in an extra turn
- **THEN** the step resets `HEAD` to the `wip:` commit, and the commit of the step folds the `wip:` commit and the work of the extra turn

#### Scenario: A failed check after the reset
- **WHEN** the agent commits its work and a later exit check fails
- **THEN** the step reports stopped with the reason of that check, not with the class `head_moved`, makes no commit, and the checkout is back at its last `wip:` commit, or at the commit where the step started when it made none

#### Scenario: A reset that fails
- **WHEN** the agent moved `HEAD` and `git reset --soft` to the expected head exits with a status other than 0
- **THEN** the step reports stopped with the class `head_moved`, and the reason names the reset command, its exit status and the output of git

### Requirement: The verification commands of a group are the code spans of its Verification lines
The verification commands of a group SHALL be the code spans of the `Verification:` lines of its tasks that start with `$ `, with the mark removed, each one once, in the order of the file. Every other code span of such a line SHALL be prose. The step SHALL run each command as a list of words, never through a shell, and SHALL stop with the reason when the first word is not a program of the verification list or the `!` of a negative search in the fixed shape.

#### Scenario: Two lines name one command
- **WHEN** two tasks of the group name `$ uv run devops ci test tests/test_sample.py` and the second names `$ uv run devops docs check` as well
- **THEN** the step runs `uv run devops ci test tests/test_sample.py` once and `uv run devops docs check` once, in that order

#### Scenario: A prose code span beside a marked command
- **WHEN** a task holds a `Verification:` line with the code span `tagged_image` and the code span `$ pytest tests/roadmap/test_step_files.py`
- **THEN** the commands of the group are `pytest tests/roadmap/test_step_files.py` only

#### Scenario: A line with no mark
- **WHEN** a task holds a `Verification:` line with the code span `pytest tests/roadmap/test_step_files.py` and no mark
- **THEN** the group has no command from that line

#### Scenario: A marked command that the step refuses
- **WHEN** a task holds the code span `$ nosuchprogram --version` on its `Verification:` line
- **THEN** the step stops with a reason that names `nosuchprogram` as a program that is not in the allowed list

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

### Requirement: The shell tool admits only the project's programs
The shell tool SHALL run a command only when its first word is a program of `SHELL_PROGRAMS` and it holds no operator that starts a second command, no redirect to a file in a read-only program, and no refused argument or `$` word in `find`. Any other command SHALL come back as a normal tool result that holds the refusal and a hint, and the run SHALL go on. A refusal SHALL add no tool retry. The shell SHALL run with `HOME` set to a temporary directory. The shell is no security boundary.

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

#### Scenario: A read-only program
- **WHEN** the model calls the shell tool with `grep -rn shout src`, `cat README.md`, `ls src`, `head -n 5 README.md` or `find src -name "*.py"`
- **THEN** the command runs and the call returns its output

#### Scenario: A file command
- **WHEN** the model calls the shell tool with `rg shout src`
- **THEN** the refusal names the tool `grep`

#### Scenario: A find that runs or deletes
- **WHEN** the model calls the shell tool with `find . -name "*.py" -exec rm {} +`
- **THEN** the refusal names `find` and `-exec`, says to use `find` to list paths only, and no process starts

#### Scenario: A redirect to a file
- **WHEN** the model calls the shell tool with `grep -rn x src > out.txt`, `cat a >> b` or `ls > f`
- **THEN** the refusal names the program and the redirect, says to use `write_file` or `edit_file`, counts as a refused command, and no process starts. `2>&1` and `>/dev/null` still run.

#### Scenario: A find with an expansion
- **WHEN** the model calls the shell tool with `find . -ex${U}ec echo {} +`, because the shell expands `${U}` after the check
- **THEN** the refusal names `find` and the word, and no process starts

#### Scenario: A change of directory
- **WHEN** the model calls the shell tool with `cd src`
- **THEN** the refusal says that `cd` is not needed because every command runs in the checkout

#### Scenario: The retry limit is unchanged
- **WHEN** the model calls the shell tool with `python -V` in more replies than `CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES`, and then ends its run
- **THEN** each call returns the refusal with its hint as a tool result and not as a retry, the run is not stopped for retries, and the limit of `CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES` still holds for the failures of a tool

#### Scenario: A real failure of a tool still counts
- **WHEN** the model calls `read_file` without its `path` argument in more replies than `CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES`
- **THEN** the run ends stopped with the tool retry limit as before

#### Scenario: The prompt and the table agree
- **WHEN** the prompt of the step is built, the shell is configured, or `docs/ROADMAP_WORKFLOW.md` is read
- **THEN** the programs and the refusals in the prompt and the document are the text that `SHELL_PROGRAMS` and `SHELL_REFUSALS` give, the allowlist of the shell is the names of `SHELL_PROGRAMS`, and a shell command of the prompt holds no operator that the shell refuses

### Requirement: The shell admits a read pipe and the checkout prefix
The shell tool SHALL run a command with a pipe when each stage after the first is a program of `CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS` that writes no file. It SHALL read a `|` in quotes or after a backslash as part of a word. It SHALL run a command that starts with the exact prefix `cd <checkout> &&` without that prefix. `|` SHALL stay in `CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS`.

#### Scenario: A read pipe
- **WHEN** the model calls the shell tool with `git status | head -n 5`, `git show HEAD:README.md | head -100`, `head -n 170 README.md | tail -n 20` or `git status | head | wc -l`
- **THEN** the command runs and the call returns its output

#### Scenario: A pattern with an alternation
- **WHEN** the model calls the shell tool with `grep -n 'shutil\|subprocess' README.md` or `grep -n "a|b" README.md`
- **THEN** the command runs, because the pipe character is part of a word

#### Scenario: A pipe to another program
- **WHEN** the model calls the shell tool with `git status | sh`, `ls | head | sh` or `ls |& head`
- **THEN** the call returns a refusal that names the program or the operator and lists `CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS`, and no process starts

#### Scenario: A pipe that writes a file
- **WHEN** the model calls the shell tool with `git status | head > out.txt`
- **THEN** the call returns the refusal of the redirect for `head`, and no process starts

#### Scenario: Another operator after a read pipe
- **WHEN** the model calls the shell tool with `git status | head; ls`
- **THEN** the call returns a refusal that names the operator `;`, and no process starts

#### Scenario: The checkout prefix
- **WHEN** the model calls the shell tool with `cd <checkout> && git status | head` and `<checkout>` is the checkout of the step
- **THEN** the command runs without the prefix

#### Scenario: Another chain with a change of directory
- **WHEN** the model calls the shell tool with `cd <checkout> && git status && ls`, or with `cd src && ls`
- **THEN** the call returns a refusal, and no process starts

#### Scenario: The pipe stays a denied operator
- **WHEN** a test reads `CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS` and `CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS`
- **THEN** the first holds `|`, and the second holds `head`, `tail`, `grep` and `wc` and only programs of `SHELL_PROGRAMS` with access `read`

### Requirement: A run that reaches a limit ends stopped
`UsageLimits` SHALL cap a run, extra turn included, at `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests and `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` tool calls. A run that reaches a limit, exceeds the retries of a tool, or has more than `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS` shell refusals in the step, SHALL end as stopped, and the step SHALL reset the checkout. The reason SHALL hold the class and the `message` of the error, masked and cut to `CONST_ROADMAP_RUN_ERROR_CHARS` characters.

#### Scenario: A model that never ends
- **WHEN** the model calls a tool in every reply
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: ` and holds the message of the error, the model got `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests at most, and the checkout is reset

#### Scenario: A model that calls too many tools
- **WHEN** the model calls more tools than `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` before it reaches the request limit
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `, and the checkout is reset

#### Scenario: The tools of the agent
- **WHEN** the step makes its first request
- **THEN** the function tools offered are `edit_file`, `grep`, `list_files`, `read_file`, `run_command` and `write_file`, and no `delegate_task`

#### Scenario: The extra turn shares the budget
- **WHEN** the first turn used all but one of the model requests and the extra turn needs two
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `, and the model got `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests at most over both turns

#### Scenario: A model that keeps calling a refused program
- **WHEN** the model calls the shell tool with `pytest tests/test_sample.py` in every reply
- **THEN** the model gets `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS` refusals as tool results, the next call ends the run, the step reports stopped with a reason that starts with `UnexpectedModelBehavior: Too many commands refused by policy in one step: the limit is` and the limit, and the checkout is reset

#### Scenario: The stop of the refusal limit is a refused tool
- **WHEN** the step stops because the shell refused more commands than the limit
- **THEN** the failure class of the reason is `refused_tool`

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
The step SHALL return a `StepOutcome` with the status (done or stopped), the reason, the last message of the agent, the commit, the repair rounds used, and the requests, the tool calls and the tokens that the run spent. The command SHALL print it as a table, or as JSON with `--format json`, and SHALL exit 1 when the status is stopped. The step SHALL record the spend of the run as one record of the spend ledger.

#### Scenario: A stopped step as JSON
- **WHEN** a step stops on a failed verification and the command runs with `--format json`
- **THEN** the output is one JSON object with `status` `stopped`, the reason, an empty `commit`, and the counts of requests, tool calls and tokens, and the exit code is 1

#### Scenario: The spend record
- **WHEN** a step ends after two model requests
- **THEN** the spend ledger holds one record for the run with the sum of the tokens of the two replies

#### Scenario: The tool calls
- **WHEN** a step ends after three tool calls in two replies
- **THEN** the outcome holds `tool_calls` 3

#### Scenario: The repair rounds
- **WHEN** a step ends after one extra turn
- **THEN** the outcome holds `repair_rounds` 1 and the table shows the count

### Requirement: A fix step makes a failed check pass
The step SHALL accept a fix request: the name of a failed check and its log. The group of a fix step SHALL be "Make check `<name>` pass", with the verification commands of every group of the change. The inputs SHALL hold the log cut to `CONST_ROADMAP_IMPLEMENT_LOG_CHARS` characters from its end. The exit checks SHALL be those of a group, except that no task is ticked and `tasks.md` SHALL be as it was. A done fix step SHALL commit as `Make check <name> pass (#N)`.

#### Scenario: A fix step with a long log
- **WHEN** a fix request holds a log longer than the limit
- **THEN** the first message of the step holds the last characters of the log up to the limit, and the first characters are not in it

#### Scenario: The fix step ticks a task
- **WHEN** the model of a fix step ticks or edits a task in `tasks.md`, and changes a source file
- **THEN** the step reports done, and the commit holds the source file and `tasks.md` as it was

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

### Requirement: A stopped step reads a bounded diff that may hold bytes that are not UTF-8
A stopped step SHALL give `mask_secrets` at most `CONST_ROADMAP_IMPLEMENT_DIFF_READ_CHARS` characters of the diff, a multiple of `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS`, and SHALL set `diff_cut` when git printed more. It SHALL read the output of git with a replacement character for each byte that is not UTF-8, and SHALL raise no decode error.

#### Scenario: A very large diff
- **WHEN** the discarded work is longer than `CONST_ROADMAP_IMPLEMENT_DIFF_READ_CHARS` characters
- **THEN** `mask_secrets` gets at most that many characters, the diff of the outcome is cut to `CONST_ROADMAP_IMPLEMENT_DIFF_CHARS` characters and `diff_cut` is true

#### Scenario: A file that is not UTF-8
- **WHEN** the discarded work holds a Latin-1 file
- **THEN** the step reports stopped with a diff that holds a replacement character in place of each byte that is not UTF-8, and raises no error

### Requirement: The reason of a stopped run counts the refused and the retried tool calls
A step that stops on a pydantic-ai error SHALL count the tool calls that a tool refused by its policy, by program, and the tool calls that came back as a retry for another cause. The reason SHALL end with both counts when a count is not zero. It SHALL list at most `CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS` programs, most refused first, and join the rest to `other`. A call counts as refused when the shell refused its command or an argument by its policy.

#### Scenario: The call that exceeds the limit
- **WHEN** the model is refused more often than `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS` times
- **THEN** the call that ends the run counts as refused too

#### Scenario: Refused commands
- **WHEN** the model calls the shell tool with `pytest tests/test_sample.py` in every reply, and `pytest` is not a program of the shell table
- **THEN** the reason ends with a new line and "Refused commands: pytest 31. Other retries: 0.", where 31 is `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS` plus one

#### Scenario: Refused commands of two programs
- **WHEN** the model is refused `python` four times and `cd` twice, and then another error ends the run
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
The agent SHALL write one line to the standard error stream when each tool call ends. The line SHALL hold the name of the tool, the program of the `command` argument when the tool has one, and the outcome: `ok`, `refused`, `retry` or `failed`. A shell refusal has the outcome `refused`. The program SHALL be the first word of the command when it is a program of the allowlist or of `IMPLEMENT_SHELL_REPLACEMENTS`, else `other:<digest>`. The line SHALL hold nothing else but the reason of a retry.

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
- **THEN** the line and the reason of a stopped run hold "other:" and a digest, and not the word

#### Scenario: A known program of the pipe table
- **WHEN** the model calls the shell tool with `wc -l README.md`
- **THEN** the line holds "program wc"

#### Scenario: An unknown first word
- **WHEN** the first word of a shell command is `secret-tool`, which is no known program
- **THEN** the line holds "program other:" and 12 hexadecimal characters, and holds neither `secret-tool` nor the rest of the command

#### Scenario: A digest with a key
- **WHEN** the first word is `hunter2password`, and it is no known program
- **THEN** the digest is the first 12 hexadecimal characters of an HMAC-SHA256 of the word with a random key of the process, so it is not the plain SHA-256 of the word, and the same word has the same digest in one run

#### Scenario: The checkout prefix
- **WHEN** the model calls the shell tool with `cd <checkout> && python -V`
- **THEN** the lines hold "started: python -V" and "program python", and not "program cd"

#### Scenario: A refused path
- **WHEN** the model calls `read_file` with a path outside the root
- **THEN** the standard error stream holds the line "Tool call: read_file, retry." and no part of the path

#### Scenario: A call that the tool reports as failed
- **WHEN** a tool reports a failed call
- **THEN** the standard error stream holds the line "Tool call: <tool>, failed."

### Requirement: A call with a command writes the command to the Job log before it runs
Before a call that has a `command` runs, the agent SHALL write the line `Tool call: <tool>, started: <command>`. The command SHALL be the first word and at most `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS` words, escaped and cut to `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS` characters. The line SHALL hide each secret, the value of each `name=value` word that is not a number, and each word with a space. When the first word is no known program, the command SHALL be `other`.

#### Scenario: A refused program
- **WHEN** the model calls `run_command` with `pytest tests/test_sample.py`, and then ends its run
- **THEN** the standard error stream holds the lines "Tool call: run_command, started: pytest tests/test_sample.py" and "Tool call: run_command, program pytest, refused."

#### Scenario: The line comes before the call
- **WHEN** the model calls `run_command` with `uv run pytest -n 48`, and the tool is still running
- **THEN** the standard error stream holds the line "Tool call: run_command, started: uv run pytest -n 48" and no line with an outcome

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
A run that ends on a failed model call (a `ModelAPIError` that is not a refused key) SHALL end as stopped when no tier of its ladder remains, and the step SHALL reset the checkout. The outcome of a failed turn SHALL hold the requests and the tokens that the turn spent, the failed request included, and the last text of the model, added to those of the turn before it.

#### Scenario: A model call fails in the first turn
- **WHEN** the agent writes `src/sample.py` and a new test file, and its next model call raises a `ModelAPIError`, a `ModelHTTPError` with the status 503, or a `ModelRequestTimeout`, and no tier of the ladder remains
- **THEN** the step reports stopped with a reason that starts with the class of the error, the outcome holds the masked diff of both files, the requests (the reply and the failed request) and the tokens, and the last text of the model, and the checkout is reset

#### Scenario: A model call fails in the extra turn
- **WHEN** the first turn passes every check and leaves a task unticked, and the model call of the extra turn for the ticks raises one of those errors, and no tier of the ladder remains
- **THEN** the step reports stopped with a reason that starts with the class of the error, the outcome holds the masked diff of the work of the first turn, the requests of both turns, and the last text of the first turn, and the checkout is reset

### Requirement: A change_tier failure advances the ladder
When the failure classification maps the failure to `change_tier`, or a model call fails without a key refusal, and the ladder for that step class has another tier available, the step SHALL advance to the next tier without incrementing the repair round counter.

#### Scenario: A parser failure advances to the next tier
- **WHEN** an attempt encounters an error classified as `change_tier` and another tier remains in the ladder
- **THEN** the next attempt runs on the next tier of the ladder and the repair round counter does not change

#### Scenario: A provider error advances to the next tier
- **WHEN** a model call raises a `ModelAPIError` that is not a refused key and another tier remains in the ladder
- **THEN** the next attempt runs on the next tier of the ladder and the repair round counter does not change

#### Scenario: Ladder tiers exhausted
- **WHEN** an attempt encounters an error classified as `change_tier` and no further tiers remain in the ladder
- **THEN** the step stops and resets the checkout

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
- **WHEN** the first turn fails `ruff check`, and the model call of the extra turn raises a `ModelHTTPError` with the status 401 or 403
- **THEN** `run_step` raises `AICredentialsError` and the checkout is reset

#### Scenario: A refused key in a job
- **WHEN** the model call of the first step of an item raises a `ModelHTTPError` with the status 401
- **THEN** `apply_implement` raises `AICredentialsError`, and the item gets no stop comment

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
When a model call fails with a `ModelHTTPError` of the status 400 inside an open stream that is no context window error, the step SHALL send the request again, at most `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS` times in a row. The first such failure on a tier SHALL add a message that asks for a smaller edit to the request. The next one on the same tier SHALL end the turn with no send. After the last send, the step SHALL stop with the reason of the failed call and the class `parser`.

#### Scenario: Two separate failures
- **WHEN** a model request fails with a 400 inside a stream, a good reply follows, and a later request fails the same way
- **THEN** the step stops with the class `parser`, and the later request is not sent again

#### Scenario: A new tier
- **WHEN** the first tier of the ladder ends on a second parser failure, and the first request of the next tier fails with a 400 inside a stream
- **THEN** the request is sent again with the message that asks for a smaller edit

#### Scenario: One failed send
- **WHEN** the first model request fails with a 400 inside a stream, and the second request answers with a good reply that ends the run
- **THEN** the step ends done, and the second request holds the messages of the first and one more part at its end, the message that asks for a smaller edit

#### Scenario: Every send fails
- **WHEN** every model request fails with a 400 inside a stream with the body "XML syntax error on line 75: unexpected EOF"
- **THEN** the step stops with the class `parser`, the reason holds the body, and the model got `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS` plus one requests, the last one with the smaller-edit message

#### Scenario: The work of the group stays
- **WHEN** the agent ticks the first task of a group and the verification of it passes, then two requests fail with a 400 inside a stream
- **THEN** the step stops with the class `parser`, and the branch holds the `wip:` commit of the first task

#### Scenario: Other failed model calls
- **WHEN** a model request fails with a 400 that is not inside a stream, a 503, or a 400 that is a context window error
- **THEN** the model gets no second request, and the step stops

#### Scenario: The failed send counts in the limit
- **WHEN** the replies and the failed send reach `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS`
- **THEN** the model gets no more than that many requests, and the step stops with the reason of the request limit

#### Scenario: A failure in the extra turn
- **WHEN** the model request of the extra turn for a failed static check fails once with a 400 inside a stream
- **THEN** the request is sent again with the message that asks for a smaller edit, and the extra turn ends with the check passing

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
Every test that a `.py` file under `tests/` held at the commit where the step started SHALL be in the checkout after the run, by qualified name (`test_x` or `Class.test_x`), unless `recorded_tests` gives its `path::name`. A test is a function named `test_*`. When any other test is lost, the step SHALL stop with a reason that names the file and at most `CONST_ROADMAP_IMPLEMENT_REASON_TESTS` of its tests, and SHALL give no extra turn. A file that does not parse is skipped.

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

#### Scenario: A removal that the record names
- **WHEN** the model removes `test_a`, and `recorded_tests` holds `tests/test_old.py::test_a`
- **THEN** the step reports done

#### Scenario: A rename or a move that the record names
- **WHEN** the model renames `test_a` to `test_z` or moves it to a new test file, and `recorded_tests` holds the old `path::name`
- **THEN** the step reports done

#### Scenario: A removal that the record does not name
- **WHEN** the model removes `test_a` and `test_b`, and `recorded_tests` holds only `tests/test_old.py::test_a`
- **THEN** the step reports stopped with the class `tests_lost`, and the reason names `test_b` and not `test_a`

#### Scenario: A kept task with a recorded removal
- **WHEN** the agent ticks a task whose verification passes, and the only test that it lost is in `recorded_tests`
- **THEN** the keeper makes the `wip:` commit

#### Scenario: The prompt of the step
- **WHEN** a test reads `roadmap_implement_step.md`
- **THEN** the rule of the tests names the `## Weakened checks` section, and says that an entry from the agent does not count

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
The agent of a step SHALL set the model settings `max_tokens` to the context window of the task divided by `CONST_ROADMAP_IMPLEMENT_OUTPUT_WINDOW_SHARE`, and `request_timeout` to the setting `roadmap.implement.request_timeout_seconds`. The default of the deadline SHALL be less than the timeout of the router in `k8s/llm/gateway/config.yaml`. A call that runs past the deadline SHALL end the step as stopped, and the model SHALL get no second request for it.

#### Scenario: The settings of the first request
- **WHEN** the step makes its first model request
- **THEN** the model settings of the request hold the cap, a quarter of the window, and the deadline of the setting

#### Scenario: The cap reaches the wire
- **WHEN** the agent of a step sends a request to an OpenAI chat model
- **THEN** the body of the request holds `max_completion_tokens` with the value of the cap, and no `request_timeout`

#### Scenario: The deadline is short of the router timeout
- **WHEN** a test reads `router_settings.timeout` of the gateway config
- **THEN** the default of the deadline is less than that timeout

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

### Requirement: A step removes the stray files of the agent
Before the exit checks stage the checkout, and again after the extra turn, the step SHALL unstage and delete each stray file and SHALL give it to no tool. A stray file is an untracked or added file that git does not ignore, a nested git repository, or a file that the group does not allow.

#### Scenario: A scratch file in the root
- **WHEN** the model writes `tmp_test_x.py` with an unused import in the checkout root, writes the files of the group, ticks the tasks, and ends its run
- **THEN** the step reports done, the file is not in the tree or in the commit, no tool got its name, and `removed` lists `tmp_test_x.py`

#### Scenario: A new test file in the directory of the group
- **WHEN** the model writes `tests/test_sample_more.py` next to the named `tests/test_sample.py`
- **THEN** the step keeps the file, and the commit holds it

#### Scenario: A file of the project directories that the plan does not list
- **WHEN** the model writes `tests/data.json`, `tests/conftest.py` and `src/helper.py`, which the group does not name
- **THEN** the step keeps the files, ends done, and the commit holds them

#### Scenario: A nested git repository
- **WHEN** the model runs `git init sub` and writes `sub/a.txt`
- **THEN** the step removes `sub/` with its files, lists `sub/` in `removed`, and ends done

#### Scenario: A fix step
- **WHEN** a fix step runs and the model writes a new file outside `src/`, `tests/`, `docs/` and `openspec/`
- **THEN** the step deletes the file

#### Scenario: A fix step with a new test file
- **WHEN** a fix step runs and the model writes a new file under `tests/` that the plan names
- **THEN** the step keeps the file and stages it

#### Scenario: A staged stray file
- **WHEN** the agent stages a new file outside `src/`, `tests/`, `docs/` and `openspec/` with `git add`
- **THEN** the step unstages the file and deletes it, in a group step and in a fix step

#### Scenario: A staged rename into a stray name
- **WHEN** the agent renames `src/other.py` to `tmp_test_x.py` with `git mv`
- **THEN** the step unstages and deletes `tmp_test_x.py`, and puts back `src/other.py`, so that the commit and the work in progress keep the file

#### Scenario: A file in a directory that the group does not name
- **WHEN** the model writes `scripts/probe.py`, which the group does not name
- **THEN** the step deletes the file

#### Scenario: The agent is told
- **WHEN** a scratch file was removed and `ruff check` fails on a file of the group
- **THEN** the message of the extra turn names the removed file and says that the group does not name it

#### Scenario: A stray file in the extra turn
- **WHEN** the model writes a scratch file in the extra turn
- **THEN** the step deletes it, and does not stop for a file that it had not changed

#### Scenario: An ignored file
- **WHEN** the model writes a file under `.data/agent/scratch/`
- **THEN** the step does not list it, deletes nothing, and the commit holds no such file

#### Scenario: The paths that a group allows
- **WHEN** the group names a path in a code span, and the model writes files under its change folder, under `src/`, `tests/`, `docs/` or `openspec/`, and at the named path
- **THEN** the step keeps those files, and it names each removed file in the Job log, in `StepOutcome.removed` and in the extra turn

### Requirement: The type check of a step is the type check of the gate
The step SHALL run `mypy` on the changed Python files under the paths of the type check of `devops ci`, with the options of that check. It SHALL take the paths and the options from the same definition as the row `typecheck` of `devops ci`. It SHALL run no type check on a changed file outside those paths, and no `mypy` when no changed file is inside them. It SHALL run `ruff check` and `ruff format` on every changed Python file.

#### Scenario: A test file with old type errors
- **WHEN** the model changes a test file that has type errors of its own, `mypy` would fail on that file, and the other exit checks pass
- **THEN** the step reports done, no `mypy` command ran, and `ruff check` ran on the test file

#### Scenario: A source file with a new type error
- **WHEN** the model changes a file under `src/` and a test file, and `mypy` fails on the source file
- **THEN** the command of `mypy` names only the source file, and the step runs its one extra turn with the text of the failure

#### Scenario: The step and the gate agree
- **WHEN** the step type-checks a file under each path of the gate
- **THEN** the command line of the step is the command line of the row `typecheck` with the files in place of the paths

### Requirement: The hooks of the repository are an exit check
After the static checks, the step SHALL run the `pre-commit` stage of the hooks over the staged changes. The child SHALL hold no GitHub token and SHALL have `PRE_COMMIT_HOME` under the data directory. The step SHALL install no git hook. The stage SHALL read the configuration that the job gives the step, a copy of the default branch, with `--config`. The step SHALL run no hook when the job gives it none.

#### Scenario: No hook configuration
- **WHEN** the repository holds no `.pre-commit-config.yaml` and the checks pass
- **THEN** the step reports done and runs no `pre-commit` command

#### Scenario: A configuration that the agent edits
- **WHEN** the agent writes `repos: []` to `.pre-commit-config.yaml`
- **THEN** every call of the stage names the copy of the configuration of the default branch with `--config`

#### Scenario: No git hook
- **WHEN** a step ends done
- **THEN** the checkout holds no `pre-commit` or `pre-push` file in its git hooks directory, and the child that ran the hooks got no variable that matches `*TOKEN*`

### Requirement: A hook that fixes a file runs again, and exit 1 is the only repairable failure
When a hook changes a file, the step SHALL stage the changed files and run the stage once more. Exit code 1 of the second run SHALL be a failure that the agent may repair, with the output of the hooks as its text. Any other non-zero exit code SHALL stop the step with the output.

#### Scenario: A hook changes a file
- **WHEN** a hook adds the missing newline at the end of a changed file and exits 1, and the second run exits 0
- **THEN** the step reports done, the commit holds the file with the newline, and the model got no extra turn

#### Scenario: A hook fails
- **WHEN** the `pre-commit` stage exits 1 on both runs
- **THEN** the failure goes to the extra turn with the output of the hooks, and the turn may change only the files that the step changed

#### Scenario: A broken environment
- **WHEN** the `pre-commit` stage exits 3
- **THEN** the step reports stopped with the output as the reason, and the model gets no extra turn

#### Scenario: A stage that runs out of time
- **WHEN** the `pre-commit` stage runs out of time
- **THEN** the step reports stopped with a reason that says the command ran out of time, the model gets no extra turn, and the checkout is reset

### Requirement: The routes name the documents of a group
The step SHALL add the named sections of a routed document to the message when a path that the group names in a code span matches a route. Each document has its own heading and is cut to `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens. Each route SHALL name a row of the "Where to look" table of `AGENTS.md` that links its document.

#### Scenario: A group that changes a test
- **WHEN** a group names `tests/test_sample.py`
- **THEN** the message holds the section "Doubles" of `docs/TESTING.md`

#### Scenario: A group that changes only a manifest
- **WHEN** a group names only `k8s/sample.yaml`
- **THEN** the message holds a section of `k8s/README.md` and holds nothing of `docs/TESTING.md`

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

### Requirement: The time limits of the implement job are settings
The settings `roadmap.implement.request_timeout_seconds`, `roadmap.implement.command_timeout_seconds` and `roadmap.implement.monitor_timeout_seconds` SHALL set the seconds that a model call, a command and the watch of the checks of a pull request may take. Each SHALL have a variable named `DEVOPS_CLI_` and the key in upper case. The defaults SHALL be 1200, 1800 and 3600, and a value below 1 SHALL be refused. A reader SHALL ask for the value when it runs.

#### Scenario: The defaults
- **WHEN** no config file and no variable sets a time limit
- **THEN** the call deadline is 1200 seconds, the command limit is 1800 seconds and the watch limit is 3600 seconds

#### Scenario: A config file and a variable
- **WHEN** the config file sets `command_timeout_seconds` to 90 and the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS` holds 120
- **THEN** the command limit is 90 and the watch limit is 120

#### Scenario: A limit of zero
- **WHEN** the config file sets a time limit to 0
- **THEN** loading the settings fails and the message names the setting

#### Scenario: A model call
- **WHEN** the config file sets `request_timeout_seconds` to 77 and a step makes its first model request
- **THEN** the model settings of the request hold `request_timeout` 77

#### Scenario: A scoped check
- **WHEN** the config file sets `command_timeout_seconds` to 41 and the job runs the scoped checks
- **THEN** each command runs with the limit 41, and a command that runs out of time fails its check with a reason that names 41 seconds

#### Scenario: The watch of the checks
- **WHEN** the config file sets `monitor_timeout_seconds` to 123 and the checks of the pull request are still pending
- **THEN** the watch waits at most 123 seconds, and the reason of the stop names 123 seconds

### Requirement: A negative search is a verification command in a fixed shape
The step SHALL run a verification command that starts with `!` only as `! git grep [options] <literal> [--] <path>...` or as `! git grep [options] -e <literal> [-e <literal>]... -- <path>...`, with at least one path and with the options `-n -I -F -i -w -l -c -q` in words of those letters. The step SHALL start no process for a command outside the shape, and the reason of the stop SHALL say which rule of the shape the command breaks.

#### Scenario: A command that is not the fixed shape
- **WHEN** a Verification line names `! rm -rf src/`, `! git grep -n name src/ | cat`, `! git grep -n name src/ ; ls`, `! git grep -n name src/ && ls`, `! git grep -n name src/ > out.txt`, `! git grep -n '$(id)' src/`, `! git grep -O name src/`, `! git grep --no-index -n name src/`, `! git grep -f patterns.txt src/`, `! git grep --open-files-in-pager=cat name src/`, `! git grep -n name /etc` or `! git grep -n name ../other`
- **THEN** the step stops with the reason that says which rule of the shape the command breaks, and starts no process

#### Scenario: A letter outside ASCII
- **WHEN** a Verification line names a literal with a fullwidth `ｆ` or an accented `é`, or a path with one
- **THEN** the step stops with the reason that the text is not a literal, or that the word is not a path, and starts no process

### Requirement: The literal and the paths of a negative search are plain
The literal SHALL hold only letters, digits, spaces and the signs `_ . : / = @ + , # % ~ -`. A path SHALL be relative, SHALL hold only letters, digits and the signs `_ . + @ ~ * / -`, SHALL NOT start with `-`, and SHALL NOT have a `..` part.

#### Scenario: A literal or a path that is not plain
- **WHEN** a Verification line names `! git grep -n 'a|b' src/` or `! git grep -n name :(top)src`
- **THEN** the step stops with the reason that names the text or the word, and starts no process

### Requirement: A negative search passes when git finds no match
The step SHALL run a negative search as `git grep` with the options, the literal, `--` and the paths, with no shell. The search SHALL pass when git exits 1, also when a path matches no file. It SHALL stop the step with the matching lines when git exits 0, and with the status when git exits with any other status.

#### Scenario: A name that is gone
- **WHEN** a Verification line names `! git grep -n absent_name src/ tests/` and no file holds `absent_name`
- **THEN** the step runs `git grep -n absent_name -- src/ tests/` and the verification command passes

#### Scenario: A name that is still there
- **WHEN** a Verification line names `! git grep -n hello src/ tests/` and `src/sample.py` holds `hello`
- **THEN** the step stops with the reason that the command found a match, with the matching lines

#### Scenario: A search that fails
- **WHEN** git exits 128 for the search
- **THEN** the step stops with the reason that holds the status, and the search is no pass

#### Scenario: A path that matches no file
- **WHEN** a Verification line names `! git grep -n hello missing/` and no tracked file is under `missing/`
- **THEN** the step runs `git grep -n hello -- missing/` and the verification command passes

### Requirement: The shell of the agent refuses a command that starts with a bang
The shell of the agent SHALL NOT run a command whose first word is `!`. Only the verification commands of the step run a negative search. The refusal SHALL say to run `git grep -n <literal> -- <paths>`, to read no output as a pass, and that the step runs a verification command that starts with `!` itself. The prompt of the step SHALL say the same.

#### Scenario: The shell of the agent
- **WHEN** the agent runs `! git grep -n x src/` in its shell
- **THEN** the shell refuses the command as a program that is not in the allowed list, the refusal holds the `git grep` form and the sentence that the step runs the `!` command itself, and no process starts

### Requirement: A verification command has a limit and a reason that is safe to show
The words of a verification command of any program SHALL hold at most 2000 characters in all, and no word SHALL hold a NUL byte or a character that does not encode to UTF-8. A word, a command and the output of a command that a reason names SHALL be escaped and cut, so that the reason holds no raw control character, no line or paragraph separator and no bidi override. The stop reason SHALL show the command cut to 2000 characters.

#### Scenario: A search that is too long
- **WHEN** a Verification line names `! git grep -n` followed by a literal of 300000 characters and `src/`
- **THEN** the step stops with the reason that the command is longer than 2000 characters, shows the command cut to 2000 characters, and starts no process

#### Scenario: A word with a control character
- **WHEN** a Verification line names `! git grep -n` followed by a quoted literal that holds a NUL byte or a line break
- **THEN** the reason shows the word with the escapes `\x00` or `\n`, and holds no NUL byte and no line break

#### Scenario: A command of another program that is too long
- **WHEN** a Verification line names `grep -n zz` or `uv run devops ci test` followed by a word of 300000 characters
- **THEN** the step stops with the reason that the command is longer than 2000 characters, and starts no process

#### Scenario: A command with a control character in the outcome of a step
- **WHEN** a Verification line of a `tasks.md` names `curl` followed by ESC, a right-to-left override (U+202E) and `@octocat`
- **THEN** `outcome.reason` of the step shows the command with the escapes `\x1b` and `\u202e`, and holds no control, format, line separator or paragraph separator character

#### Scenario: The output of a command
- **WHEN** a verification command fails, or a negative search finds a line, and the output holds ESC, U+202E and NEL
- **THEN** the reason shows the output with the escapes `\x1b`, `\u202e` and `\x85`, and holds none of the raw characters

#### Scenario: A word that cannot be an argument
- **WHEN** a Verification line names `grep a` followed by a NUL byte, or a word with a lone surrogate
- **THEN** the step stops with the reason that a word holds a NUL byte or a character that cannot be encoded, starts no process, and raises no error

### Requirement: The log names no word after a bang
The log line of a shell call whose first word is `!` SHALL name the program `other:<digest>` and SHALL show no word after it.

#### Scenario: A bang command
- **WHEN** the agent calls the shell with `! Authorization: Bearer abcdef0123456789abcdef`
- **THEN** the log line says `program other:` and a digest, and holds no word of the command

### Requirement: A group is a heading at the top level of the file
The step SHALL take a `## <n>. <title>` heading as the start of a group only when the heading is at the top level of `tasks.md`. A heading inside a list item or a quote SHALL be text of that item.

#### Scenario: A heading in a list item
- **WHEN** `tasks.md` holds the group 1 and, after it, a list item `- ## 2. Extra` with a task under it
- **THEN** the parsed groups are the group 1 only

#### Scenario: A heading in a quote
- **WHEN** `tasks.md` holds a quote `> ## 2. Extra` after the group 1
- **THEN** the parsed groups are the group 1 only

### Requirement: A step records its model calls and its tool calls
When the job gives a step a trace, the step SHALL add one event for each model call, with the model name, the input and output tokens and the seconds, and one event for each tool call, with the tool, the program, the digest of its masked argument and the outcome `ok`, `refused`, `retry` or `failed`. A retry SHALL hold the reason that the Job log shows.

#### Scenario: Two model calls
- **WHEN** a step ends after two model replies of 100 and 120 input tokens
- **THEN** the trace holds two `model` events with those input tokens, the model name and a number of seconds from the time of each request and its reply

#### Scenario: A refused command and a retried edit
- **WHEN** the model runs a command that the shell policy refuses, and an `edit_file` whose `old_text` is missing
- **THEN** the trace holds a `tool` event with the outcome `refused` and the program, and a `tool` event with the outcome `retry` and the reason of the tool

#### Scenario: The digest of an argument
- **WHEN** the model makes the same call twice and a third call with another command
- **THEN** the first two events hold the same digest of 12 hexadecimal characters, the third holds another, and no event holds the command

### Requirement: A step records its checks and its retries
The step SHALL add one event for each command that it runs as an exit check, with the command and its exit status, and one event for each repair round and each send again of a model request, with the reason.

#### Scenario: A failed lint and one repair round
- **WHEN** `ruff check` exits 1 on the files of a step, a repair round fixes them, and the check exits 0
- **THEN** the trace holds a `check` event with exit status 1, a `retry` event with the reason, and a `check` event with exit status 0, in that order

#### Scenario: A command that runs out of time
- **WHEN** a check command exceeds the command timeout
- **THEN** the `check` event holds no exit status and says that it timed out

### Requirement: Every text of an event is masked
The step SHALL pass each text of an event through `bounded_text` and `mask_private_hosts` and escape it to one line, and SHALL build the digest from the argument with each secret-named value hidden. An event SHALL hold no secret and no private host name.

#### Scenario: A secret and a host in a reason
- **WHEN** the reason of a retry holds `Bearer abcdefghijklmnopqrstuvwxyz0123` and `db.corp.internal`
- **THEN** the event holds `<masked-token>` and `<masked-host>`, and neither original text

#### Scenario: A secret-named argument
- **WHEN** two calls differ only in the value of the argument `api_key`
- **THEN** their events hold the same digest and neither value

### Requirement: A step keeps a ticked task whose verification passes
When the agent ticks a task of the group, the step SHALL run the verification commands of that task, as the text of the `tasks.md` before the run gives them. When they pass, or the task has none, the step SHALL commit the checkout as `wip: <done> of <total> tasks of group <n>, <title> (#<issue>)` and tell its caller through `on_wip`. A task that fails its verification SHALL NOT be kept, and a fix step SHALL keep nothing.

#### Scenario: Two tasks, one ticked
- **WHEN** the model writes the test, ticks the first task, writes the code of the second task, ends without a tick for it, and the verification command `uv run devops docs check` of the group exits 1 at the exit
- **THEN** the step reports stopped, the checkout holds one `wip:` commit with the test and the first task ticked, the code of the second task is gone, and `on_wip` was called once with 1 of 2

#### Scenario: A task that fails its verification
- **WHEN** the model ticks the first task and its verification command exits 1
- **THEN** the step makes no `wip:` commit and calls no `on_wip`

#### Scenario: A lint error after the last tick
- **WHEN** the model ticks every task, each verification passes, and `ruff check` fails at the exit
- **THEN** the step reports stopped, and the checkout holds one `wip:` commit with the work and the ticks

### Requirement: A work-in-progress commit holds the tasks file of the job
The `wip:` commit SHALL hold the `tasks.md` as it was before the run with the ticks that the step verified, and no stray file of the group. The step SHALL make no `wip:` commit that would lose a test that existed at the start, unless the caller of the step gives its `path::name` in `recorded_tests`. The agent SHALL find its own `tasks.md` in the checkout after the commit.

#### Scenario: A test that the work would lose
- **WHEN** the model replaces a test file with a file that holds fewer of its tests, and ticks a task, and `recorded_tests` does not name the lost tests
- **THEN** the step runs no verification command at the tick and makes no `wip:` commit

#### Scenario: A stray file
- **WHEN** the model writes a file outside `src/`, `tests/`, `docs/` and `openspec/` and ticks a task
- **THEN** the `wip:` commit does not hold that file

### Requirement: A step that ends done folds its work in progress into its commit
A step that starts on a branch with `wip:` commits and ends done SHALL make one commit, titled `<group title> (#N)`, that holds all the work since the last commit that is no `wip:` commit. The branch SHALL then hold no `wip:` commit of that step. The exit checks SHALL judge all the work since that commit.

#### Scenario: A second step finishes the group
- **WHEN** a step stopped after a `wip:` commit, and a second step ticks the remaining task
- **THEN** the second step reports done, the message of its first request shows the kept task ticked, and the branch holds one new commit past the start, which does not start with `wip:`

### Requirement: The budgets of a step and of an item are settings
The settings `roadmap.implement.step_token_budget`, `item_token_budget`, `step_time_limit_seconds` and `item_time_limit_seconds` SHALL set the input tokens and the seconds that a step and a run of an item may use. Each SHALL have a variable named `DEVOPS_CLI_` and the key in upper case. The defaults SHALL be 8000000, 20000000, 5400 and 12600.

A value below 1 SHALL be refused. An item time limit above `roadmap.implement.deadline_ceiling_seconds` SHALL be refused too.

#### Scenario: The defaults
- **WHEN** no config file and no variable sets a budget
- **THEN** the step budget is 8000000 tokens, the item budget is 20000000 tokens, the step limit is 5400 seconds and the item limit is 12600 seconds

#### Scenario: A variable
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_BUDGET` holds 5000
- **THEN** the step budget is 5000

#### Scenario: A budget of zero
- **WHEN** the config file sets `step_token_budget` to 0
- **THEN** loading the settings fails and the message names the setting

#### Scenario: An item limit above the ceiling of the Job
- **WHEN** the config file sets `item_time_limit_seconds` above `deadline_ceiling_seconds`
- **THEN** loading the settings fails and the message names `item_time_limit_seconds`

### Requirement: A step that spends a budget stops and names it
Before each model request, the step SHALL compare its input tokens and its seconds with the budgets of the step and of the item. When one is spent, the step SHALL make no request, stop with the class `limit_reached` and name the setting and its value, unless the rule `implement.extension` extends the token budget of the step. The item budget SHALL count the tokens of the earlier steps, and the item limit the seconds since the run began. The step SHALL reset the checkout as for any stop.

#### Scenario: The token budget of the step
- **WHEN** `step_token_budget` is 50, the first reply of the model reports more than 50 input tokens, and the step made fewer than 20 tool calls
- **THEN** the step reports stopped with the class `limit_reached`, the model got no second request, and the reason names `roadmap.implement.step_token_budget` and 50

#### Scenario: The token budget of the item
- **WHEN** the earlier steps of the run used 900 input tokens and `item_token_budget` is 1000
- **THEN** a step stops after its first reply, and the reason names `roadmap.implement.item_token_budget` and 1000

#### Scenario: The time limit of the step
- **WHEN** `step_time_limit_seconds` is 60 and the clock shows 61 seconds since the step began
- **THEN** the step makes no further request, stops with the class `limit_reached`, and the reason names `roadmap.implement.step_time_limit_seconds` and 60

#### Scenario: The time limit of the item
- **WHEN** the run began 100 seconds ago and `item_time_limit_seconds` is 60
- **THEN** the step makes no request and the reason names `roadmap.implement.item_time_limit_seconds` and 60

#### Scenario: Within the budgets
- **WHEN** a step uses less than every budget
- **THEN** the step is not stopped for a budget

#### Scenario: A repair turn
- **WHEN** the first turn used the whole time limit of the step and a check fails
- **THEN** the repair turn makes no request and the step stops with the class `limit_reached`

### Requirement: The stop of the repair rounds names the setting
When a step stops with a failure that a repair round could have taken, and all the rounds are used, the reason SHALL end with a line that names `roadmap.implement.repair_rounds` and its value.

#### Scenario: The rounds are used
- **WHEN** `ruff check` still exits 1 after every round and `repair_rounds` is 2
- **THEN** the reason names `ruff check` and then holds a line with `roadmap.implement.repair_rounds=2`

#### Scenario: A failure with no round
- **WHEN** a verification command exits 1, which gets no repair round
- **THEN** the reason holds no line about the repair rounds

### Requirement: A failure that no attempt can fix gets no repair round
A failure of the class `plan_defect` or `premise_false` SHALL get no repair round, whatever the setting `repair_rounds` is. The step SHALL stop with the evidence of the failure. Only a failed static check or hook gets a round.

#### Scenario: A group that changes no file
- **WHEN** the model ends its run and changes no file of a group
- **THEN** the step reports stopped with the class `plan_defect`, the model got one run and no extra turn, and the trace holds one attempt

### Requirement: A step records each attempt
The step SHALL add one `attempt` event to the trace for the first run and for each repair round. The event SHALL hold the number of the attempt, the tier, the outcome `passed` or `failed`, the failure class of a failed attempt, its evidence, and `repair` or `stop` for what follows. The evidence SHALL pass the masking of every text of an event.

#### Scenario: A failing check that passes on the second attempt
- **WHEN** `ruff check` exits 1 after the first run, and the model fixes the file in the repair round
- **THEN** the trace holds two `attempt` events: attempt 1 failed with class `lint` and the evidence of `ruff`, followed by `repair`, and attempt 2 passed

#### Scenario: A stop
- **WHEN** the repair rounds are used and the check still fails
- **THEN** the last `attempt` event is failed and followed by `stop`

#### Scenario: A fatal class
- **WHEN** the group changes no file
- **THEN** the trace holds one `attempt` event, failed with class `plan_defect` and followed by `stop`

### Requirement: A behavior group's tests fail on the base commit

The implement step SHALL replay the test files of a behavior group on the base commit of the group, with the tests of the head overlaid. The step SHALL accept the group only when one test of those files fails in its call phase on the base commit.

#### Scenario: Tests pass on base

- **WHEN** every test of the test files of a behavior group passes on the base commit
- **THEN** the step stops with a message that names the test files, and it gets a repair round of `roadmap.implement.repair_rounds` that may change only test files.

#### Scenario: Tests error on base

- **WHEN** a test file of a behavior group stops with an error on the base commit, before any assertion runs, and no test of the group fails there
- **THEN** the step stops with a message, and the error does not count as a failure on the base commit.

#### Scenario: A test fails on base

- **WHEN** a test of a behavior group fails in its call phase on the base commit and passes after the change
- **THEN** the step continues with the other exit checks.

#### Scenario: No test file changed

- **WHEN** a behavior group changes no test file
- **THEN** the step stops with a message and gets no repair round.

### Requirement: The trace holds each base replay

The implement step SHALL add one check event to the trace for each replay of a behavior group on the base commit. The event SHALL hold the exit status of the replay.

#### Scenario: A replay is a check event

- **WHEN** the step replays the tests of a behavior group on the base commit
- **THEN** the trace holds one check event for the replay, with its exit status.

### Requirement: The PR comment shows the fail-to-pass result of each behavior group

The PR comment of a step SHALL show one line for each behavior group that the step replayed on the base commit. The line SHALL name the group, the result on the base commit and the tests that failed there.

#### Scenario: A behavior group is replayed

- **WHEN** the step replays a behavior group on the base commit, and the group then passes or stops
- **THEN** the PR comment holds one line that names the group, the result of the replay and the failed test.

### Requirement: A group of kind other records its verify output

The implement step SHALL keep the output of each verification command of a group of kind `other` that passes. The PR comment SHALL show each command with its exit status and its masked, bounded output.

#### Scenario: A verify command of an other group prints a line

- **WHEN** a group of kind `other` passes its verify command, and the command prints one line
- **THEN** the step outcome holds that command, its exit status and that line.

### Requirement: The job ticks the tasks of a group whose exit checks pass
When every exit check of a group step passes, the job SHALL tick each unticked task of the group in the `tasks.md` of the change, and SHALL stage the file, so that the commit holds the ticks. The job SHALL tick a task that the model did not tick. A group with no verification command SHALL be ticked when its exit checks pass. A fix step SHALL tick no task. A step whose exit check fails SHALL write no tick.

#### Scenario: A passing group with no tick from the model
- **WHEN** the model writes the test file and the source file of group 1, ticks no task, and the verification command, `ruff` and `mypy` exit 0
- **THEN** the step reports done, and the commit holds the test file, the source file and `tasks.md` with the tasks of group 1 ticked

#### Scenario: A group with no verification command
- **WHEN** group 1 has no `Verification:` line, the model writes its files and ticks no task, and `ruff` and `mypy` exit 0
- **THEN** the step reports done, and the commit holds the tasks of group 1 ticked

#### Scenario: A failed check after the work
- **WHEN** the model writes the files and ticks no task, and `ruff check` exits 1 in every turn
- **THEN** the step reports stopped, the checkout holds no tick, and the checkout is reset

#### Scenario: A fix step
- **WHEN** a fix step ends with a changed file and no ticks
- **THEN** the step commits the fix, and the job ticks no task

#### Scenario: A tasks file that holds no group to tick
- **WHEN** the `tasks.md` of the change holds no group with the number of the step when the exit checks pass
- **THEN** the step reports stopped with the reason that the job cannot tick the group, and the checkout is reset

### Requirement: A step asks for a fix of a failed static check or hook within the repair rounds
When the agent ends its run, each verification command passes, and `ruff check`, `mypy --strict` or a hook fails, the step SHALL run one more turn in the same conversation under the same `UsageLimits`, while a repair round is left. Its message SHALL hold the failure text, masked and cut to `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters. Every exit check SHALL run again after each turn. With no round left the step SHALL stop with the last failure.

#### Scenario: An unused import
- **WHEN** the model ticks the tasks and ends its run, `ruff check` exits 1 for an unused import in a changed file, and the model removes the import in the extra turn
- **THEN** the step reports done, the extra turn got the text of the failure, the commit holds the file without the import, `ruff check` ran twice, and `repair_rounds` is 1

#### Scenario: The failure stays
- **WHEN** `ruff check` still exits 1 after every round, and `repair_rounds` is 3
- **THEN** the step reports stopped with the reason that names `ruff check` and its exit status, the model got three extra turns and no fourth, and the checkout is reset

#### Scenario: A failed type check
- **WHEN** `mypy --strict` exits 1 after the first turn, and the model fixes the file in the extra turn
- **THEN** the step reports done, and the extra turn got the text of the failure of `mypy`

#### Scenario: A failure with a task left unticked
- **WHEN** `ruff check` exits 1 after the first turn, and a task of the group is unticked
- **THEN** the message of the extra turn holds the text of the failure and no list of tasks, and the job ticks the group when the repair passes the checks

#### Scenario: A failed verification command
- **WHEN** a verification command exits 1
- **THEN** the model gets no extra turn for it

#### Scenario: A failure after the repair turn
- **WHEN** the extra turn for the failed check ends and `ruff check` exits 1
- **THEN** the model gets another turn that holds the text of the failure, while a round is left

#### Scenario: No round
- **WHEN** `repair_rounds` is 0 and `ruff check` exits 1
- **THEN** the model gets no extra turn and the step reports stopped with the reason that names `ruff check`

#### Scenario: A fix step
- **WHEN** a fix step ends with a changed file and `ruff check` exits 1
- **THEN** the model gets an extra turn that holds the text of the failure and no list of ticks

#### Scenario: The extra turn shares the budget
- **WHEN** the first turn used all but one of the model requests and the extra turn needs two
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `

#### Scenario: A hook fails
- **WHEN** the `pre-commit` stage exits 1 for a `pytest.raises` with no `match` in a changed test, and the model adds the `match` in the extra turn
- **THEN** the step reports done, the message of the extra turn holds the output of the hook, and the commit holds the fixed test

#### Scenario: A hook that the agent cannot fix
- **WHEN** the `pre-commit` stage exits 1 after every turn, and `repair_rounds` is 3
- **THEN** the step reports stopped with the reason that holds the output of the hook, the model got three extra turns, `repair_rounds` is 3, and the checkout is reset

### Requirement: A negative search takes repeated -e literals
The step SHALL read each `-e` option of a negative search as the option that takes the literal after it. Each such literal SHALL hold only the characters of a positional literal and SHALL NOT start with `-`. The step SHALL run `git grep` with each literal after its own `-e`, and SHALL pass the search when git exits 1.

#### Scenario: Two names that do not occur
- **WHEN** a Verification line names `! git grep -n -e "ImagetoolsFake" -e "inspect_command" -- src tests` and no file under `src` or `tests` holds either name
- **THEN** the step runs `git grep -n -e ImagetoolsFake -e inspect_command -- src tests` and the verification command passes

#### Scenario: One of the names occurs
- **WHEN** a Verification line names `! git grep -n -e hello -e absent_name -- src/ tests/` and `src/sample.py` holds `hello`
- **THEN** the step stops with the matching lines that git printed, and starts no other process

#### Scenario: A value that is not a plain literal
- **WHEN** a Verification line names `! git grep -n -e 'a|b' -- src/`, `! git grep -n -e 'a;b' -- src/` or `! git grep -n -e -- src/`
- **THEN** the step stops with the reason that names the text, or that the `-e` option has no literal, and starts no process

#### Scenario: A value that starts with -
- **WHEN** a Verification line names `! git grep -n -e -E -- src/` or `! git grep -n -e --addons -- src/`
- **THEN** the step stops with the reason that the text starts with `-`, and starts no process

### Requirement: A negative search with -e puts -- before its paths
A negative search with `-e` options SHALL have `--` after its last literal and before its paths. It SHALL NOT have a word between the last literal and `--`.

#### Scenario: Both forms in one line
- **WHEN** a Verification line names `! git grep -e name literal -- src/`, or `! git grep -e name src/`
- **THEN** the step stops with the reason that names both forms of the search, and starts no process

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

### Requirement: A fix step changes only the paths that the plan names
A fix step SHALL stop with the class `outside_plan` when it changed, added or deleted a path that the plan does not name. The plan names a path in a code span of the text of any group of its `tasks.md`, which includes the `Reads:` line, the `Changes:` line and the tasks. A file under the change folder of the item is always allowed. The stop SHALL reset the checkout, SHALL name each path in its reason, and SHALL run no repair round. A group step SHALL NOT be subject to this rule.

#### Scenario: A fix step edits a path that the plan does not name
- **WHEN** a fix step writes `src/sample.py`, which the plan names, and `src/other.py`, which it does not
- **THEN** the step reports stopped with the class `outside_plan`, the reason names `src/other.py` and not `src/sample.py`, the diff holds the edit of `src/other.py`, no repair round ran, and the checkout is at its start commit

#### Scenario: A fix step adds an unnamed file
- **WHEN** a fix step writes a new file `tests/test_sample_fix.py` that the plan does not name
- **THEN** the step reports stopped with the class `outside_plan`

#### Scenario: A fix step deletes an unnamed file
- **WHEN** a fix step deletes `src/other.py`, which the plan does not name
- **THEN** the step reports stopped with the class `outside_plan`, and the file is back in the checkout

#### Scenario: A fix step edits only named paths and the change folder
- **WHEN** a fix step edits `src/sample.py`, which the plan names, and `design.md` of the change folder
- **THEN** the step ends done

### Requirement: The ladder names only the step classes that a step reads
The step classes SHALL be `edit`, which is a group of a change, and `repair`, which is the fix of a failed check. The setting `roadmap.implement.ladder` SHALL hold a tier list for each of these two classes by default, and SHALL refuse a key that is not one of them, with a message that names the key and the classes.

#### Scenario: The default ladder
- **WHEN** the settings are read with no ladder set
- **THEN** the ladder holds the keys `edit` and `repair`, and no other key

#### Scenario: A removed class is named
- **WHEN** the ladder names the key `plan` or `review`
- **THEN** the settings are refused with a message that the ladder names no step class with that key

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

### Requirement: A step records the form check in its trace
The implement step SHALL record one check event for each test-form check, and the event SHALL name the test file, the named count, the collected count and the result.

#### Scenario: The trace holds the form check
- **WHEN** the step checks a test that a task names
- **THEN** the trace holds a check event with the test file and the named and collected counts.

#### Scenario: A task names no count
- **WHEN** the task names a parametrized test with no case count
- **THEN** the check event names the test file and the collected count and records the result.

### Requirement: The events of a trace stand in the order of the run
The step SHALL add the model event of a reply when the reply comes, so that the events stand in the order of the run: a reply, then the tool calls that it asks for. A reply that the step never receives whole, such as one that the output cap cut, SHALL get its event when its turn ends.

#### Scenario: The order of the events
- **WHEN** a step ends after a reply with one tool call, a reply with two tool calls and a last reply
- **THEN** the kinds of the events are `model`, `tool`, `model`, `tool`, `tool`, `model`, then the `attempt` event

#### Scenario: A long run
- **WHEN** a step makes 101 requests and 150 tool calls, and the events do not fit `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` characters
- **THEN** the encoded trace is not longer than the bound, it holds no `model` event, it holds the newest `tool` events in the order of the run and then the `attempt` event, and `dropped` counts the 101 model events and the older tool events

### Requirement: A shell call in a trace holds its exit status
The `tool` event of a `run_command` call SHALL hold `status`, the exit code of the command, and no text of its output: the code of the last line `[exit code: <n>]`, else 0. A call whose command ran past its wait, a refused call and a call of another tool SHALL hold no `status`.

#### Scenario: The exit status of a shell call
- **WHEN** the result of a `run_command` call ends with the line `[exit code: 128]`
- **THEN** the `tool` event holds `status` 128 and no text of the output

#### Scenario: A command that exits with 0
- **WHEN** the result of a `run_command` call has no line of an exit code
- **THEN** the `tool` event holds `status` 0

#### Scenario: A shell call with no status
- **WHEN** the result of a `run_command` call ends with the line of the timeout
- **THEN** the `tool` event holds no `status`

### Requirement: The ceiling of a step budget is a setting
The setting `roadmap.implement.step_token_ceiling` SHALL set the most input tokens that a step may reach with its one extension. It SHALL have the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING`. Its default SHALL be 16000000, twice the default step budget. A ceiling below `roadmap.implement.step_token_budget` SHALL be refused.

#### Scenario: The default ceiling
- **WHEN** no config file and no variable sets the ceiling
- **THEN** the ceiling is 16000000 tokens

#### Scenario: A variable for the ceiling
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING` holds 9000000
- **THEN** the ceiling is 9000000

#### Scenario: A ceiling below the step budget
- **WHEN** the config file sets `step_token_budget` to 5000 and `step_token_ceiling` to 4999
- **THEN** loading the settings fails and the message names `step_token_ceiling`

### Requirement: A step that makes progress gets one extension of its token budget
When a step reaches `roadmap.implement.step_token_budget` and no other budget is spent, the step SHALL read the digest of its last 20 tool calls from its tool log. With at least 1 successful edit and at most 3 refused commands, the step SHALL raise its token budget one time by 50 percent of the budget, up to `roadmap.implement.step_token_ceiling`, and go on. The rule is the only resolver of the decision point `implement.extension`, and no decision model takes part.

#### Scenario: The shapes of pilot 3 that a person finished
- **WHEN** a step reaches a budget of 50 tokens with the counts (successful edits, refused commands) of one of the 16 stops of pilot 3 that a person finished later, from (1, 3) to (10, 0)
- **THEN** the budget is not spent, and the extension holds a budget of 75 tokens and those counts

#### Scenario: The ceiling cuts the extension
- **WHEN** `step_token_budget` is 50, `step_token_ceiling` is 60 and the step makes progress at its budget
- **THEN** the extension holds a budget of 60 tokens and says that the ceiling cut it

### Requirement: The digest of progress holds counts of the tool log
The digest SHALL count, in the last 20 tool calls of the step over all its turns and tiers, the successful edits (a `write_file` or an `edit_file` call with the outcome ok) and the refused commands (a call with the outcome refused). A log with fewer than 20 tool calls SHALL give no digest. The digest SHALL hold counts only.

#### Scenario: The counts of the last calls
- **WHEN** the log holds 21 calls: an `edit_file` with the outcome ok, 15 reads, a `write_file` with the outcome ok, an `edit_file` with the outcome retry, a `write_file` that failed and 2 refused shell calls
- **THEN** the digest holds 20 calls, 1 successful edit and 2 refused commands, because the first edit is out of the window

#### Scenario: A short log
- **WHEN** the log holds 19 calls
- **THEN** the log gives no digest

### Requirement: The Job log and the outcome show the extension
The step SHALL write one line to the Job log that names the rule `implement.extension`, the old and the new budget, and the counts. The outcome of the step SHALL hold the extension: the old budget, the new budget, the counts and whether the ceiling cut it.

#### Scenario: A step that edits at its budget
- **WHEN** `step_token_budget` is 50 and the first reply makes 20 tool calls with 3 successful edits
- **THEN** the model gets a second request, the step ends done, and the Job log names the extension from 50 to 75 input tokens with 3 successful edits and 0 refused commands

### Requirement: A step with no progress at its token budget stops as before
The step SHALL stop with the class `limit_reached` at its token budget, and SHALL name `roadmap.implement.step_token_budget` and its value, when its tool log gives no digest, when the digest holds no successful edit or more than 3 refused commands, when the ceiling leaves no room above the tokens already used, or when the step already used its extension. A step SHALL decide one time at each limit.

#### Scenario: The shapes of pilot 3 that repeated refused commands
- **WHEN** a step reaches a budget of 50 tokens with the counts (0, 11), (1, 10), (0, 16), (1, 4) or (0, 9)
- **THEN** the step stops, and the reason names `roadmap.implement.step_token_budget=50` and the counts in its last 20 tool calls

#### Scenario: A step that repeats refused commands
- **WHEN** `step_token_budget` is 50 and the first reply makes 20 tool calls with 4 refused commands and no edit
- **THEN** the model gets no second request, the step stops with the class `limit_reached`, and the outcome holds no extension

#### Scenario: The item budget holds
- **WHEN** a step got its extension and then reaches `item_token_budget` before the end of the extension
- **THEN** the step stops with the class `limit_reached`, and the reason names `roadmap.implement.item_token_budget`

### Requirement: The reason of a stop at the token budget names its cause
The reason of a stop at the token budget SHALL give the counts of the digest, say that the log holds fewer than 20 tool calls, name the ceiling and its value, or name the new budget of the extension.

#### Scenario: A short log at the budget
- **WHEN** a step reaches its budget after 3 tool calls
- **THEN** the step stops with the class `limit_reached`, and the reason says that the log holds fewer than 20 tool calls

#### Scenario: The second limit
- **WHEN** an extended step reaches its new budget of 75 tokens
- **THEN** the step stops with the class `limit_reached`, and the reason names `roadmap.implement.step_token_budget=50` and the extension to 75 input tokens

#### Scenario: The ceiling ends the extension
- **WHEN** the ceiling of 60 tokens cut the extension and the step reaches 60 tokens
- **THEN** the step stops, and the reason names `roadmap.implement.step_token_ceiling=60`

#### Scenario: The ceiling leaves no room
- **WHEN** `step_token_ceiling` is equal to `step_token_budget` and the step makes progress at its budget
- **THEN** the step stops, and the reason names `roadmap.implement.step_token_ceiling` and its value

### Requirement: The decisions of the extension are counted
Each decision of the rule `implement.extension` SHALL add 1 to `devops_cli_roadmap_implement_extension_total` with the label `decision`, `extended` or `halted`, and 0 to the other value, so the metric has 2 series. A step SHALL count at most two decisions: one extension and one stop.

#### Scenario: An extension
- **WHEN** the rule extends the budget of a step
- **THEN** the counter gets 1 for `extended` and 0 for `halted`

#### Scenario: A stop that the step asks again
- **WHEN** a halted step checks its budget again
- **THEN** the counter gets no second count

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

### Requirement: The shell of a step waits for its command up to the command limit
The agent of a step SHALL offer the tool `run_command` of the harness as its one shell tool, and no shell tool with a background mode. A call SHALL wait until its command ends, up to `roadmap.implement.command_timeout_seconds`, and the harness SHALL kill a command that runs longer. The step SHALL set the wait of each call to that setting, whatever wait the model gives. The allowlist and the refusals of the shell SHALL apply to the tool.

#### Scenario: The tools of the agent
- **WHEN** a step offers its tools to the model
- **THEN** the tools are `edit_file`, `grep`, `list_files`, `read_file`, `run_command` and `write_file`

#### Scenario: A wait from the model
- **WHEN** `roadmap.implement.command_timeout_seconds` is 41 and the model calls `run_command` with no wait, and with the waits 5, 99999 and 0
- **THEN** each command reaches the workspace with the wait 41, and the run goes on

### Requirement: The operator refusal names the code of python -c
The hint of a refusal for an operator SHALL state that a `;`, a new line or a heredoc in the code of `python -c` is refused too. It SHALL tell the agent to write that code to a file under `.data/agent/scratch/` and to run `uv run python <file>`.

#### Scenario: A new line in the code of python -c
- **WHEN** the model calls `run_command` with `uv run python -c` and code that holds a new line
- **THEN** the refusal names the operator, states the rule of one command in each call, and holds the hint about the code of `python -c` and the script file

### Requirement: The implement prompt gives the count of extra turns
The implement prompt SHALL state that a step has at most `roadmap.implement.repair_rounds` extra turns, with the default of that setting, and that each failed check or hook takes one. It MUST NOT promise one more turn for an error of `ruff check` or `mypy`.

#### Scenario: The prompt names the setting of the extra turns
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_implement_step.md`
- **THEN** The prompt names `roadmap.implement.repair_rounds` with its default and holds no promise of one more turn

### Requirement: The implement prompt names the refusal of a heredoc
The implement prompt SHALL state that the shell refuses a new line, a heredoc, and code of `python -c` that holds a `;` or a new line. It SHALL tell the agent to write that code to a file under `.data/agent/scratch/` and to run `uv run python <file>`. The rule SHALL win over the base instructions of `Coder`, which tell the agent to use a heredoc.

#### Scenario: The prompt names the heredoc before the first call
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_implement_step.md`
- **THEN** The prompt names a heredoc, `python -c`, a new line, a `;`, `.data/agent/scratch/` and `uv run python <file>`, and the shell refuses a new line and a `;`
