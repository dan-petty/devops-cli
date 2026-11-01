## ADDED Requirements

### Requirement: A command run from a deleted working directory stops with one error line
When a command registered on a `new_typer()` app starts and the working directory of the process no longer exists, the command SHALL print one error line that says the working directory does not exist, SHALL exit with status 1, and SHALL print no traceback. The command body SHALL not run. A command group that shows its help SHALL still print the help.

#### Scenario: A command starts after its working directory was removed
- **WHEN** the working directory of the process is removed and a person runs a command of a `new_typer()` app
- **THEN** the command exits with status 1, prints one line that says the working directory does not exist, prints no traceback, and does not run its body

#### Scenario: A command group shows its help
- **WHEN** the working directory of the process is removed and a person runs `devops gh --help`
- **THEN** the command prints the help of the group and exits with status 0
