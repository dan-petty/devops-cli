## ADDED Requirements

### Requirement: The intake evaluation runs in the eval group
The CLI SHALL run the intake duplicate evaluation as `devops roadmap eval intake`, and MUST NOT register `devops roadmap intake-eval` as a command or as an alias.

#### Scenario: The eval group holds intake
- **WHEN** A user runs `devops roadmap eval intake --help`.
- **THEN** The command exits 0 and its help text names the intake duplicate evaluation.

#### Scenario: The old command is gone
- **WHEN** A user runs `devops roadmap intake-eval`.
- **THEN** The command exits 2 and reports no such command.

#### Scenario: The eval group lists intake
- **WHEN** A test lists the command names of `eval_app`.
- **THEN** The names include `intake` and hold no `intake-eval`.

### Requirement: The moved evaluation keeps its options and its output
`devops roadmap eval intake` SHALL keep the `--dry-run` option, the scoring output and the exit codes of the evaluation it runs.

#### Scenario: A dry run prints the plan
- **WHEN** A user runs `devops roadmap eval intake --dry-run`.
- **THEN** The command prints the dry-run plan, makes no model call and exits 0.

#### Scenario: A scored run reports each case
- **WHEN** The evaluation runs over the committed cases.
- **THEN** It prints the score of each case with the precision and the recall of the duplicate verdict, and exits 0 when every case ran.

### Requirement: The moved command is excluded from MCP by its new path
The MCP exclusion list MUST hold `("roadmap", "eval", "intake")` and MUST NOT hold `("roadmap", "intake-eval")`.

#### Scenario: Every command is exposed or excluded
- **WHEN** The test `test_all_cli_commands_are_either_exposed_or_excluded` runs.
- **THEN** The test passes with no unaccounted command path and no extra command path.

### Requirement: The command reference lists the new name
The command matrix and the roadmap command reference SHALL list `devops roadmap eval intake` and MUST NOT list `devops roadmap intake-eval`.

#### Scenario: The docs check passes
- **WHEN** A developer runs `devops ci docs`.
- **THEN** The check exits 0 and the documents hold the new command name.
