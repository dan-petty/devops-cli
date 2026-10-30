# Spec Delta

## MODIFIED Requirements

### Requirement: The shell tool admits only the project's programs
The shell tool of the agent SHALL run a command only when its first word is `git`, `uv`, `ruff` or `mypy`, and the command holds none of the operators that start a second command. Any other command SHALL come back to the model as a refusal, and the run SHALL go on. The text of the refusal SHALL keep the text of the shell tool and SHALL add the replacement: the entry of `IMPLEMENT_SHELL_REPLACEMENTS` for the first word, else the list of the allowed programs with the `uv run` form, else, for an operator, the rule of one command in each call. The refusal SHALL NOT change what the shell allows. The shell SHALL run with `HOME` set to a temporary directory of the step, so that the configuration and credentials of the user's home do not reach it. The shell is no security boundary.

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
- **THEN** the refusal holds "Instead of `python`: `uv run python`", and no process starts

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
- **WHEN** the table `IMPLEMENT_SHELL_REPLACEMENTS` or `IMPLEMENT_SHELL_PROGRAMS` differs from the prompt of the step
- **THEN** a test fails

### Requirement: The reason of a stopped run counts the refused and the retried tool calls
A step that stops on a pydantic-ai error SHALL count, over all its turns, the tool calls that a tool refused by its policy, by program, and the tool calls that came back as a retry for another cause. The reason SHALL end with both counts when either is not zero. The refused count SHALL list the programs from the most refused to the least, at most `CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS` of them, and SHALL add the programs beyond that to the count of `other`. A call counts as refused when it has a shell command and a `PermissionError` is in the `__cause__` chain of the retry. The step SHALL read no message text.

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
The agent of a step SHALL write one line to the standard error stream for each tool call. The line SHALL hold the name of the tool, the program of the `command` argument when the tool has one, and the outcome: `ok`, `refused`, `retry` or `failed`. The program SHALL be the first word of the command when it is a bare word, else the word `other`. A bare word SHALL match `[A-Za-z][A-Za-z0-9_.-]{0,23}` as a whole, and the mask of secrets SHALL leave it as it is. The line SHALL hold nothing else.

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
- **WHEN** the first word of a shell command is an assignment such as `API_KEY=hunter2`, a path, a word of more than 24 characters, a word with a space or a quote, an escape sequence, or the command has an unclosed quote
- **THEN** the line holds "program other" and holds no part of the word

#### Scenario: A bare word in the form of a secret
- **WHEN** the first word of a shell command is a bare word that the mask of secrets changes
- **THEN** the line holds "program other"

#### Scenario: A refused path
- **WHEN** the model calls `read_file` with a path outside the root
- **THEN** the standard error stream holds the line "Tool call: read_file, retry."

#### Scenario: A call that the tool reports as failed
- **WHEN** a tool reports a failed call
- **THEN** the standard error stream holds the line "Tool call: <tool>, failed."
