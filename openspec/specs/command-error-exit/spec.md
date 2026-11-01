# command-error-exit Specification

## Purpose
How a devops command reports a `DevOpsCLIError` that it raises: one error line with the error's message, the error's exit status, and no traceback, through the one exit seam of `new_typer()`.

## Requirements

### Requirement: A command reports a DevOpsCLIError in one line and exits with its status
When a command registered on a `new_typer()` app raises a `DevOpsCLIError`, the command SHALL print the error's message in one error line, with any Rich markup in it shown as text, and SHALL exit with the error's `exit_code`. It SHALL print no traceback.

#### Scenario: A command raises an error with markup in its message
- **WHEN** a command raises a `DevOpsCLIError` subclass with the message `the [bold]token[/bold] was refused` and `exit_code` 7
- **THEN** the command exits with status 7, prints one line that holds `the [bold]token[/bold] was refused`, and prints no traceback

#### Scenario: A callback that runs as a command raises an error
- **WHEN** an app callback with `invoke_without_command=True` raises a `DevOpsCLIError` subclass with `exit_code` 7
- **THEN** the command exits with status 7, prints one error line, and prints no traceback

#### Scenario: A sandbox dry run refuses a workspace
- **WHEN** `devops docker sandbox --dry-run` or `devops test sandbox --dry-run` refuses a workspace that holds a protected directory
- **THEN** the command exits with the status of `DockerSandboxError`, prints the refusal that names the workspace and the protected directory, and makes no engine call

### Requirement: Every command passes through the exit seam
Every app that a `devops` command group registers SHALL be a `new_typer()` app, and no command module SHALL report a `DevOpsCLIError` itself.

#### Scenario: The registered apps
- **WHEN** the apps of every command group in `devops_cli.main` are walked
- **THEN** each app is an `OTelTyper`

#### Scenario: The command modules
- **WHEN** the modules under `src/devops_cli/commands/` are parsed
- **THEN** none passes `exit_on=`, names `exit_on_error`, or raises `typer.Exit(<error>.exit_code)` in an `except`

### Requirement: A command run from a deleted working directory stops with one error line
When a command registered on a `new_typer()` app starts and the working directory of the process no longer exists, the command SHALL print one error line that says the working directory does not exist, SHALL exit with status 1, and SHALL print no traceback. The command body SHALL not run. A command group that shows its help SHALL still print the help.

#### Scenario: A command starts after its working directory was removed
- **WHEN** the working directory of the process is removed and a person runs a command of a `new_typer()` app
- **THEN** the command exits with status 1, prints one line that says the working directory does not exist, prints no traceback, and does not run its body

#### Scenario: A command group shows its help
- **WHEN** the working directory of the process is removed and a person runs `devops gh --help`
- **THEN** the command prints the help of the group and exits with status 0
