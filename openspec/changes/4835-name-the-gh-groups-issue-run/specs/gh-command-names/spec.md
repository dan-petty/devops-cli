## Purpose

How `devops gh` names a command that does the work of a gh command, so that an agent that types the gh form reaches the command, and what a name that is not gh's does.

## ADDED Requirements

### Requirement: A devops gh command for a gh noun has the gh name
The `devops gh` group SHALL name each command that does the work of a gh command with gh's noun: `issue`, `pr`, `run`, `label`, `secret`, `project`, `api` and `status`. A plural group name and `rate_limit` SHALL be no command: each SHALL exit 2 with a usage error that names the gh name.

#### Scenario: The gh noun reaches the command
- **WHEN** user executes `devops gh issue --help`
- **THEN** the command exits 0

#### Scenario: A plural name is a usage error
- **WHEN** user executes `devops gh issues list`
- **THEN** the command exits 2 and prints `No such command 'issues'. Did you mean 'issue'?`

#### Scenario: The underscore form of rate-limit is a usage error
- **WHEN** user executes `devops gh rate_limit list`
- **THEN** the command exits 2 and prints `No such command 'rate_limit'. Did you mean 'rate-limit'`
