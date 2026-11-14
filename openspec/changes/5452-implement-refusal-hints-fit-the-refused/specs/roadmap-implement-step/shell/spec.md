## ADDED Requirements

### Requirement: A chain of allowed programs names two calls
The refusal hint of a chain of allowed programs with `&&` or `;` SHALL name each command as its own call and SHALL give two commands as an example.

#### Scenario: A refused git chain
- **WHEN** the model calls `run_command` with `git status && git log`
- **THEN** the hint names `git status --short` and `git log --oneline -5` as two separate calls

### Requirement: The pipe refusal names read_file
The refusal of a pipe to a program that the shell does not allow SHALL name `read_file` with `offset` and `limit`, and SHALL name the program after the pipe.

#### Scenario: A refused pipe to sed
- **WHEN** the model calls `run_command` with `git status | sed -n 1,20p`
- **THEN** the text names `read_file` with `offset` and `limit` and names `sed`

### Requirement: The refusal table names openspec and devops
`SHELL_REFUSALS` SHALL hold a row for `openspec` that names `uv run devops openspec check` and a row for a bare `devops` that names `uv run devops`, and `docs/ROADMAP_WORKFLOW.md` SHALL show the same rows.

#### Scenario: Rows for the project commands
- **WHEN** `SHELL_REFUSALS` and the refusal table of `docs/ROADMAP_WORKFLOW.md` are read
- **THEN** both hold an `openspec` row with `uv run devops openspec check` and a `devops` row with `uv run devops`

### Requirement: The step offers create_directory
The implement step SHALL offer a tool named `create_directory` that creates a directory inside the checkout and refuses a path outside it.

#### Scenario: A directory outside the checkout
- **WHEN** the model calls `create_directory` with `../outside`
- **THEN** the call creates no directory and returns a refusal that names the checkout

## MODIFIED Requirements

### Requirement: The python -c refusal names the write_file call first
The refusal hint of a command that runs Python code inline, with `-c` or a heredoc, SHALL start with the instruction to write that code with `write_file` to a file under `.data/agent/scratch/`, and SHALL then name the `uv run python` command of that file.

#### Scenario: A new line in the code of python -c
- **WHEN** the model calls `run_command` with `uv run python -c` and code that holds a new line
- **THEN** the hint starts with the `write_file` instruction and names `.data/agent/scratch/<name>.py` and `uv run python .data/agent/scratch/<name>.py`

#### Scenario: A separator in the code of python -c
- **WHEN** the model calls `run_command` with `uv run python -c` and code that holds a `;`
- **THEN** the hint starts with the `write_file` instruction and names `.data/agent/scratch/<name>.py` and `uv run python .data/agent/scratch/<name>.py`

#### Scenario: A heredoc in the code of python -c
- **WHEN** the model calls `run_command` with `uv run python -` and a heredoc
- **THEN** the hint starts with the `write_file` instruction and names the script file and its `uv run python` command

## RENAMED Requirements

- FROM: `### Requirement: The operator refusal names the code of python -c`
- TO: `### Requirement: The python -c refusal names the write_file call first`
