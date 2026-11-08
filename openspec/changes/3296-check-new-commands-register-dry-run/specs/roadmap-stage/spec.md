## ADDED Requirements

### Requirement: The plan registers the companions of a new command
`check_proposal` SHALL report a missing companion registration of a `devops` command that a task of a plan adds, and the report SHALL name each missing registration.

#### Scenario: A new subcommand with no companion registration
- **WHEN** A plan task says `Add devops pr evidence to src/devops_cli/commands/pr.py`, the staged `src/devops_cli/commands/pr.py` holds no `"evidence"` literal, and the plan holds no `command-dry-run-class` entry, no task for `tests/commands/test_pr_dry_run.py` and neither documentation command.
- **THEN** `check_proposal` returns one problem for each missing companion registration, and each problem names `pr evidence`.

#### Scenario: A new command with every companion registration
- **WHEN** The same plan adds a `command-dry-run-class` requirement that names `pr evidence`, a task that edits `tests/commands/test_pr_dry_run.py`, a task that runs `uv run devops docs generate --sync-readme` and a task that runs `uv run devops ci docs`.
- **THEN** `check_proposal` returns no companion registration problem.

#### Scenario: An edit of an existing command
- **WHEN** A plan task changes the help text of `devops pr list`, whose `"list"` literal the staged `src/devops_cli/commands/pr.py` holds.
- **THEN** `check_proposal` returns no companion registration problem.

#### Scenario: A command of another family in the same task
- **WHEN** A task of a group that changes `src/devops_cli/commands/pr.py` says `uv run devops ci test tests/commands/test_pr_dry_run.py`, and `ci` is not the stem of the changed module.
- **THEN** `check_proposal` reports no new command for `ci test`.

#### Scenario: A new command with no command module in the plan
- **WHEN** A plan task names `devops pr evidence` and no group of the plan changes a path under `src/devops_cli/commands/`.
- **THEN** `check_proposal` returns no companion registration problem, because no task adds the command.
