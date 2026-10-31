# command-dry-run-class Specification

## Purpose
Devops-cli commands declare their dry-run behavior so that users and agents know command side effects and run read-only operations safely.

## Requirements

### Requirement: command-declares-dry-run-class
Every command callback in devops-cli SHALL support explicit dry-run classification via the `@dry_run_class` decorator with values `request-plan` or `no-external-request`. A command marked with `request-plan` SHALL declare the `--dry-run` option.

#### Scenario: command declares request-plan class
- **WHEN** a command callback is decorated with `@dry_run_class("request-plan")`
- **THEN** inspecting the callback or Click command reveals the classification attribute `request-plan` and the command exposes `--dry-run`

### Requirement: proxy-runs-no-external-request-commands
When the user executes `devops --dry-run <command>` for a command with the `no-external-request` classification, the lazy proxy SHALL execute the command normally without `--dry-run` if the command does not declare `--dry-run`.

#### Scenario: dry run executes no-external-request command
- **WHEN** the user executes `devops --dry-run <command>` on a command marked `no-external-request`
- **THEN** the command executes without error and prints its normal output

### Requirement: ratchet-prevents-unclassified-commands
Every command path reachable from `_COMMAND_SPECS` SHALL either carry a dry-run classification or be listed in `tests/fixtures/dry_run_gaps.json`. An unclassified command missing from the gap list, or a classified command remaining in the gap list, SHALL fail the ratchet test.

#### Scenario: unclassified command not in gap list fails
- **WHEN** a new command path is added without a dry-run class and without an entry in `dry_run_gaps.json`
- **THEN** the ratchet test fails and identifies the missing command

### Requirement: mcp-read-only-hint-agrees-with-no-external-request
An MCP tool entry in `CONST_MCP_EXPOSURE_TABLE` that delegates to a command marked `no-external-request` SHALL specify `readOnlyHint` as true.

#### Scenario: mcp tool wraps no-external-request command
- **WHEN** an MCP tool definition in `CONST_MCP_EXPOSURE_TABLE` maps to a command path with `no-external-request`
- **THEN** the third element of the table entry is `True`

### Requirement: gh-project-views-pages-request-plans
The ten external-request commands in `gh project`, `gh views`, and `gh pages` SHALL carry the `request-plan` dry-run class. Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.

#### Scenario: Dry run on gh pages build
- **WHEN** user executes `devops gh pages build --dry-run`
- **THEN** no external request is made and the planned build request is printed

#### Scenario: Dry run on gh project sync
- **WHEN** user executes `devops gh project sync --dry-run`
- **THEN** no external request is made and the planned board, field, and view requests are printed

### Requirement: gh-project-views-pages-no-external-request
The five local commands in `gh project`, `gh views`, and `gh pages` SHALL carry the `no-external-request` dry-run class, allowing execution under `devops --dry-run <command>` without external requests.

#### Scenario: Dry run on local command gh views list
- **WHEN** user executes `devops --dry-run gh views list`
- **THEN** the command executes locally and renders the standardized views table

### Requirement: gh-issues-milestones-labels-runs-request-plans
The 16 external-request commands in `gh issues`, `gh labels`, `gh milestones`, `gh runs`, `roadmap run`, and `survey` SHALL carry the `request-plan` dry-run class. Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.

#### Scenario: Dry run on gh issues create
- **WHEN** user executes `devops gh issues create --title "test" --dry-run`
- **THEN** no external request is made and the planned issue create request is printed

#### Scenario: Dry run on gh milestones list
- **WHEN** user executes `devops gh milestones list --dry-run`
- **THEN** no external request is made and the planned milestones listing request is printed

#### Scenario: Dry run on roadmap run
- **WHEN** user executes `devops roadmap run --dry-run`
- **THEN** no external request is made and the planned evaluation requests are printed

#### Scenario: Dry run on survey
- **WHEN** user executes `devops survey --dry-run`
- **THEN** no external request is made and the planned survey requests are printed

### Requirement: gh-api-status-branch-protection-secrets-request-plans
The nine external-request commands in `gh api`, `gh branch-protection audit`, `gh branch-protection sync`, `gh metrics`, `gh rate-limit`, `gh secrets list`, `gh secrets sync`, `gh status`, and `status` SHALL carry the `request-plan` dry-run class. Each command SHALL expose `--dry-run`, make zero external requests during a dry run, and output its planned requests.

#### Scenario: Dry run on gh api
- **WHEN** user executes `devops gh api repos/:owner/:repo/issues --dry-run`
- **THEN** no external request is made and the planned api request is printed

#### Scenario: Dry run on gh rate-limit
- **WHEN** user executes `devops gh rate-limit --dry-run`
- **THEN** no external request is made and the planned rate_limit request is printed

#### Scenario: Dry run on gh branch-protection sync
- **WHEN** user executes `devops gh branch-protection sync --dry-run`
- **THEN** no external request is made, no remote branch protection is fetched, and planned protection requests are printed

#### Scenario: Dry run on gh secrets sync
- **WHEN** user executes `devops gh secrets sync -n TOKEN --dry-run`
- **THEN** no external request is made, OS Keyring and Vault are not accessed, and planned secret upload requests are printed

#### Scenario: Dry run on status
- **WHEN** user executes `devops status --dry-run`
- **THEN** no external HTTP request is made and planned statuspage requests are printed

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
