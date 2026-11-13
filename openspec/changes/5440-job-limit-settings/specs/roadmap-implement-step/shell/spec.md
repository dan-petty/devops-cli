## MODIFIED Requirements

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
- **WHEN** the model calls the shell tool with `python -V` in more replies than `roadmap.implement.tool_retries`, and then ends its run
- **THEN** each call returns the refusal with its hint as a tool result and not as a retry, the run is not stopped for retries, and the limit of `roadmap.implement.tool_retries` still holds for the failures of a tool

#### Scenario: A real failure of a tool still counts
- **WHEN** the model calls `read_file` without its `path` argument in more replies than `roadmap.implement.tool_retries`
- **THEN** the run ends stopped with the tool retry limit as before, and the file tools of the harness take the limit of the setting

#### Scenario: The prompt and the table agree
- **WHEN** the prompt of the step is built, the shell is configured, or `docs/ROADMAP_WORKFLOW.md` is read
- **THEN** the programs and the refusals in the prompt and the document are the text that `SHELL_PROGRAMS` and `SHELL_REFUSALS` give, the allowlist of the shell is the names of `SHELL_PROGRAMS`, and a shell command of the prompt holds no operator that the shell refuses

### Requirement: Consecutive refusals stop the step
The implement step SHALL end the run as stopped when the shell policy refuses `roadmap.implement.max_consecutive_refusals` commands in a row, and the checkout SHALL reset. Any tool call that is not refused SHALL reset the count to 0. The stop SHALL use the failure class `refused_tool`. The setting `roadmap.implement.max_consecutive_refusals` SHALL have the default 3, and the settings load SHALL refuse a value above `roadmap.implement.max_refusals`.

#### Scenario: Three refusals in a row
- **WHEN** the shell policy refuses 3 commands in a row and no tool call is accepted between them
- **THEN** the third refusal ends the run, the reason names the limit of 3, the failure class is `refused_tool`, and the checkout is reset

#### Scenario: Refusals split by an accepted call
- **WHEN** the shell policy refuses 2 commands, a tool call is accepted, and the shell policy refuses 2 more commands
- **THEN** the step does not stop for the consecutive limit
