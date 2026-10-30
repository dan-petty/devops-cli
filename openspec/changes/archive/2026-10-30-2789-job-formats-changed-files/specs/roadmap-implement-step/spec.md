# Spec Delta

## ADDED Requirements

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
