## MODIFIED Requirements

### Requirement: The shell tool admits only the project's programs
The shell tool SHALL run a command only when its first word is a program of `SHELL_PROGRAMS` and it holds no operator that starts a second command, no redirect to a file in a read-only program, and no refused argument or `$` word in `find`. Any other command SHALL come back as a refusal with a hint, and the run SHALL go on. A refused argument SHALL count as a refused command. The shell SHALL run with `HOME` set to a temporary directory. The shell is no security boundary.

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
- **WHEN** the model calls the shell tool with `python -V` in every reply
- **THEN** the model got five refusals with a hint, and the sixth call ends the run as before

#### Scenario: The prompt and the table agree
- **WHEN** the prompt of the step is built, the shell is configured, or `docs/ROADMAP_WORKFLOW.md` is read
- **THEN** the programs and the refusals in the prompt and the document are the text that `SHELL_PROGRAMS` and `SHELL_REFUSALS` give, the allowlist of the shell is the names of `SHELL_PROGRAMS`, and a shell command of the prompt holds no operator that the shell refuses

### Requirement: The reason of a stopped run counts the refused and the retried tool calls
A step that stops on a pydantic-ai error SHALL count the tool calls that a tool refused by its policy, by program, and the tool calls that came back as a retry for another cause. The reason SHALL end with both counts when a count is not zero. It SHALL list at most `CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS` programs, most refused first, and join the rest to `other`. A call counts as refused when it has a shell command and a `PermissionError` is in its `__cause__` chain.

#### Scenario: The call that exceeds the limit
- **WHEN** the model is refused more often than `CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES` times
- **THEN** the call that ends the run counts as refused too

#### Scenario: Refused commands
- **WHEN** the model calls the shell tool with `pytest tests/test_sample.py` in every reply, and `pytest` is not a program of the shell table
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
