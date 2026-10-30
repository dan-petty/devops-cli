# Spec Delta

## MODIFIED Requirements

### Requirement: Every tool call of a step writes one line to the Job log
The agent of a step SHALL write one line to the standard error stream for each tool call, when the call ends. The line SHALL hold the name of the tool, the program of the `command` argument when the tool has one, and the outcome: `ok`, `refused`, `retry` or `failed`. The program SHALL be the first word of the command when it is a program of the allowlist or a program of `IMPLEMENT_SHELL_REPLACEMENTS`, else the word `other`. Before a call that has a `command` runs, the agent SHALL write the line `Tool call: <tool>, started: <command>`. The command SHALL be the first word and the words after it, at most `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS` words, with secrets masked, control characters escaped, and cut to `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS` characters. When the first word is not a known program, the command SHALL be the word `other`. No line SHALL hold a path or a content of a call that has no `command`, or any output.

#### Scenario: A refused program
- **WHEN** the model calls the shell tool with `pytest tests/test_sample.py`, and then ends its run
- **THEN** the standard error stream holds the lines "Tool call: shell, started: pytest tests/test_sample.py" and "Tool call: shell, program pytest, refused."

#### Scenario: A program of the allowlist
- **WHEN** the model calls a tool with the command `git status`
- **THEN** the lines hold "started: git status" and "program git"

#### Scenario: The line comes before the call
- **WHEN** the model calls the shell tool with `uv run pytest -n 48`, and the tool is still running
- **THEN** the standard error stream holds the line "Tool call: shell, started: uv run pytest -n 48" and no line with an outcome

#### Scenario: A long command
- **WHEN** the command has more words than `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS`, or more characters than `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS`
- **THEN** the line holds the first words, cut, and ends with " ..."

#### Scenario: A secret in an argument
- **WHEN** the command is `git remote add origin https://user:ghp_<token>@example.com/x.git`, with a GitHub token in place of `<token>`
- **THEN** the line holds no part of the token

#### Scenario: A control character in an argument
- **WHEN** an argument holds a line break or an escape sequence
- **THEN** the line is one line, and it holds the escaped form of the character

#### Scenario: A call that returns
- **WHEN** the model calls `write_file` with a path and a content, and then ends its run
- **THEN** the standard error stream holds the line "Tool call: write_file, ok." and holds neither the path nor the content

#### Scenario: A call that fails validation
- **WHEN** the model calls `read_file` without its `path` argument
- **THEN** the standard error stream holds the line "Tool call: read_file, retry."

#### Scenario: A first word that is no program
- **WHEN** the first word of a shell command is an assignment such as `API_KEY=hunter2`, a path, a word with a space or a quote, an escape sequence, or the command has an unclosed quote
- **THEN** the lines hold "started: other" and "program other" and hold no part of the command

#### Scenario: A short bare word that is no known program
- **WHEN** the first word of a shell command is a short bare word such as `hunter2password` that the model read from a file
- **THEN** the lines and the reason of a stopped run hold "other" and not the word

#### Scenario: A refused path
- **WHEN** the model calls `read_file` with a path outside the root
- **THEN** the standard error stream holds the line "Tool call: read_file, retry."

#### Scenario: A call that the tool reports as failed
- **WHEN** a tool reports a failed call
- **THEN** the standard error stream holds the line "Tool call: <tool>, failed."

## ADDED Requirements

### Requirement: The shell of a step takes the worker bound of the process
The shell of a step SHALL get `PYTEST_XDIST_AUTO_NUM_WORKERS` with the value of the process when the process has it, and SHALL not set it otherwise.

#### Scenario: The process has the variable
- **WHEN** the process sets `PYTEST_XDIST_AUTO_NUM_WORKERS` to `2`
- **THEN** the environment of the shell holds the same value

#### Scenario: The process has no variable
- **WHEN** the process does not set it
- **THEN** the environment of the shell does not hold it
