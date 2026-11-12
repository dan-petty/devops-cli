## Purpose

The `devops tf notify-plan` command formats an OpenTofu plan as a collapsible pull request comment and prints it. It sends no request, and its words say so.

## ADDED Requirements

### Requirement: Notify-plan prints the comment and sends no request

`devops tf notify-plan` SHALL format the plan text as a collapsible comment and print it, and SHALL send no request. With `--json`, it SHALL print the `pr` number, the counts and the comment. When the plan file is not given or does not exist, it SHALL print the fixed sample plan `Plan: 2 to add, 1 to change, 0 to destroy.`. Its docstring and the help of `--pr` and `--plan-file` SHALL say this.

#### Scenario: Comment for a pull request number

- **WHEN** `devops tf notify-plan --plan-file plan.txt --pr 42 --json` runs and `plan.txt` holds `No changes.`
- **THEN** it prints the `pr` 42, the counts 0, 0 and 0, and the comment that holds `No changes.`, and it makes no request

#### Scenario: No plan file

- **WHEN** `devops tf notify-plan --json` runs with no `--plan-file`
- **THEN** it prints the counts 2, 1 and 0 and the comment that holds the sample plan
