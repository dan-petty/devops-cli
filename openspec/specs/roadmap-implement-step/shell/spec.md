# roadmap-implement-step/shell Specification

## Purpose
The shell tool of an implement step: the programs and the pipes that it admits, the commands that it refuses, the worker bound and the command limit.

## Requirements

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

### Requirement: The shell of a step takes the worker bound of the process
The shell of a step SHALL get `PYTEST_XDIST_AUTO_NUM_WORKERS` with the value of the process when the process has it, and SHALL not set it otherwise.

#### Scenario: The process has the variable
- **WHEN** the process sets `PYTEST_XDIST_AUTO_NUM_WORKERS` to `2`
- **THEN** the environment of the shell holds the same value

#### Scenario: The process has no variable
- **WHEN** the process does not set it
- **THEN** the environment of the shell does not hold it

### Requirement: The shell of the agent refuses a command that starts with a bang
The shell of the agent SHALL NOT run a command whose first word is `!`. Only the verification commands of the step run a negative search. The refusal SHALL say to run `git grep -n <literal> -- <paths>`, to read no output as a pass, and that the step runs a verification command that starts with `!` itself. The prompt of the step SHALL say the same.

#### Scenario: The shell of the agent
- **WHEN** the agent runs `! git grep -n x src/` in its shell
- **THEN** the shell refuses the command as a program that is not in the allowed list, the refusal holds the `git grep` form and the sentence that the step runs the `!` command itself, and no process starts

### Requirement: The log names no word after a bang
The log line of a shell call whose first word is `!` SHALL name the program `other:<digest>` and SHALL show no word after it.

#### Scenario: A bang command
- **WHEN** the agent calls the shell with `! Authorization: Bearer abcdef0123456789abcdef`
- **THEN** the log line says `program other:` and a digest, and holds no word of the command

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

### Requirement: The implement prompt names the refusal of a heredoc
The implement prompt SHALL state that the shell refuses a new line, a heredoc, and code of `python -c` that holds a `;` or a new line. It SHALL tell the agent to write that code to a file under `.data/agent/scratch/` and to run `uv run python <file>`. The rule SHALL win over the base instructions of `Coder`, which tell the agent to use a heredoc.

#### Scenario: The prompt names the heredoc before the first call
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_implement_step.md`
- **THEN** The prompt names a heredoc, `python -c`, a new line, a `;`, `.data/agent/scratch/` and `uv run python <file>`, and the shell refuses a new line and a `;`

### Requirement: Consecutive refusals stop the step
The implement step SHALL end the run as stopped when the shell policy refuses `CONST_ROADMAP_IMPLEMENT_MAX_CONSECUTIVE_REFUSALS` commands in a row, and the checkout SHALL reset. Any tool call that is not refused SHALL reset the count to 0. The stop SHALL use the failure class `refused_tool`. The constant `CONST_ROADMAP_IMPLEMENT_MAX_CONSECUTIVE_REFUSALS` SHALL be 3.

#### Scenario: Three refusals in a row
- **WHEN** the shell policy refuses 3 commands in a row and no tool call is accepted between them
- **THEN** the third refusal ends the run, the reason names the limit of 3, the failure class is `refused_tool`, and the checkout is reset

#### Scenario: Refusals split by an accepted call
- **WHEN** the shell policy refuses 2 commands, a tool call is accepted, and the shell policy refuses 2 more commands
- **THEN** the step does not stop for the consecutive limit
