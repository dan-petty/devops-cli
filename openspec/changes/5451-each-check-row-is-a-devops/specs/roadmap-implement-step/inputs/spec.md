## MODIFIED Requirements

### Requirement: The prompt lists the local commands of the catalog
The prompt of the step SHALL list each command of `LOCAL_COMMANDS` with its access class and its use, and `docs/ROADMAP_WORKFLOW.md` SHALL hold the same table. `LOCAL_COMMANDS` SHALL hold `ci test`, `ci constructs`, `ci docs`, `ci openspec`, `ai repomap`, `ai ast`, `docs generate` and `openspec check`, and no `network` command. A listed command run through `uv run` SHALL pass the shell policy and SHALL NOT count as a refusal.

#### Scenario: The prompt holds the table
- **WHEN** The prompt of the step is built.
- **THEN** It holds the text of `local_commands_table()` and no placeholder.

#### Scenario: The document holds the table
- **WHEN** `docs/ROADMAP_WORKFLOW.md` is read.
- **THEN** It holds the text of `local_commands_table()`.

#### Scenario: A new command is missing from the prompt
- **WHEN** A command is added to `LOCAL_COMMANDS` and the prompt file or the document does not hold it.
- **THEN** The consistency test fails and names the missing command.

#### Scenario: A listed command exists
- **WHEN** The test runs `--help` for each command of `LOCAL_COMMANDS` on the `devops` app.
- **THEN** Each command exits with status 0.

#### Scenario: A listed command is no refusal
- **WHEN** The model calls the shell tool with `uv run devops ai repomap`.
- **THEN** The command reaches the process edge, the refusal counter is unchanged, and no refusal comes back.

## RENAMED Requirements

- FROM: `### Requirement: The prompt lists the local devops commands of the catalog`
- TO: `### Requirement: The prompt lists the local commands of the catalog`
