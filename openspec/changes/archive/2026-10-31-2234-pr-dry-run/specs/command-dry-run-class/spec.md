# command-dry-run-class Specification

## ADDED Requirements

### Requirement: pr-commands-request-plans
The seventeen external-request commands in `pr check-readiness`, `pr checks`, `pr close`, `pr create`, `pr diff`, `pr edit`, `pr hardening-report`, `pr list`, `pr monitor`, `pr ready`, `pr threads list`, `pr threads reply`, `pr threads resolve`, `pr threads resolve-all`, `pr threads unresolve`, `pr view`, and `pr wait` SHALL carry the `request-plan` dry-run class. Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.

#### Scenario: Dry run on pr list
- **WHEN** user executes `devops pr list --dry-run`
- **THEN** no external request is made and the planned pull requests query is printed

#### Scenario: Dry run on pr view
- **WHEN** user executes `devops pr view 123 --dry-run`
- **THEN** no external request is made and the planned pull request view is printed

#### Scenario: Dry run on pr checks
- **WHEN** user executes `devops pr checks 123 --dry-run`
- **THEN** no external request is made and the planned checks query is printed

#### Scenario: Dry run on pr monitor
- **WHEN** user executes `devops pr monitor 123 --dry-run`
- **THEN** no external request is made and the repeated monitoring requests are printed

#### Scenario: Dry run on pr edit
- **WHEN** user executes `devops pr edit 123 --title "new title" --dry-run`
- **THEN** no external request is made and the planned edit request is printed

#### Scenario: Dry run on pr create
- **WHEN** user executes `devops pr create --title "feat: new feature" --dry-run`
- **THEN** no external request is made and the planned draft creation and labeling requests are printed

#### Scenario: Dry run on pr ready
- **WHEN** user executes `devops pr ready 123 --dry-run`
- **THEN** no external request is made and the planned verification and ready conversion requests are printed

#### Scenario: Dry run on pr diff
- **WHEN** user executes `devops pr diff 123 --dry-run`
- **THEN** no external request is made and the planned diff request is printed

#### Scenario: Dry run on pr close
- **WHEN** user executes `devops pr close 123 --dry-run`
- **THEN** no external request is made and the planned close request is printed

#### Scenario: Dry run on pr check-readiness
- **WHEN** user executes `devops pr check-readiness 123 --dry-run`
- **THEN** no external request is made and the planned readiness validation requests are printed

#### Scenario: Dry run on pr hardening-report
- **WHEN** user executes `devops pr hardening-report --pr 123 --dry-run`
- **THEN** no external request is made and the planned audit query is printed

#### Scenario: Dry run on pr threads commands
- **WHEN** user executes `devops pr threads list 123 --dry-run` or `devops pr threads reply tid "reply" --dry-run` or `devops pr threads resolve tid --dry-run` or `devops pr threads unresolve tid --dry-run` or `devops pr threads resolve-all 123 --dry-run`
- **THEN** no external request is made and the planned GraphQL requests are printed
