## MODIFIED Requirements

### Requirement: Notify-plan prints the comment and sends no request

`devops tf notify-plan` SHALL format the plan text as a collapsible comment and print it, and
SHALL send no request. With `--json`, it SHALL print the `pr` number, the counts and the comment.
It SHALL read each of the adds, changes and destroys from its own `N to <action>` segment of the
plan text. A plan with no such segment SHALL report zero for each count.

#### Scenario: Comment for a pull request number

- **WHEN** `devops tf notify-plan --plan-file plan.txt --pr 42 --json` runs and `plan.txt` holds `No changes.`
- **THEN** it prints the `pr` 42, the counts 0, 0 and 0, and the comment that holds `No changes.`, and it makes no request

#### Scenario: A plan with five adds, three changes and one destroy

- **WHEN** the plan file holds `Plan: 5 to add, 3 to change, 1 to destroy.` and the caller passes `--json`
- **THEN** the JSON output holds `"adds": 5`, `"changes": 3` and `"destroys": 1`

#### Scenario: A plan that imports one resource and changes two

- **WHEN** the plan file holds `Plan: 1 to import, 0 to add, 2 to change, 0 to destroy.` and the caller passes `--json`
- **THEN** the JSON output holds `"adds": 0`, `"changes": 2` and `"destroys": 0`

#### Scenario: A plan that matches the configuration

- **WHEN** the plan file holds `No changes. Your infrastructure matches the configuration.` and the caller passes `--json`
- **THEN** the JSON output holds `"adds": 0`, `"changes": 0` and `"destroys": 0`

#### Scenario: The table output for a plan with other counts

- **WHEN** the plan file holds `Plan: 5 to add, 3 to change, 1 to destroy.` and the caller runs the command with no `--json`
- **THEN** the printed comment holds `+5 ~3 -1` and holds no `+2 ~1 -0`

## ADDED Requirements

### Requirement: Notify-plan requires an existing plan file

`devops tf notify-plan` SHALL require `--plan-file`, read the text it holds, and refuse a path that
does not exist. A missing path, and a call without the option, SHALL exit non-zero with an error
that names the path or the option.

#### Scenario: A missing plan file

- **WHEN** the caller runs `devops tf notify-plan --plan-file no-such-file.txt --json`
- **THEN** the exit code is not 0, the error text holds `no-such-file.txt`, and no plan summary is printed

#### Scenario: No plan file

- **WHEN** `devops tf notify-plan --json` runs with no `--plan-file`
- **THEN** the exit code is not 0 and the error text names `--plan-file`
