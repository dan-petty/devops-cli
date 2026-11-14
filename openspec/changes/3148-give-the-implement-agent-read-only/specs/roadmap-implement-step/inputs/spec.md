## ADDED Requirements

### Requirement: The implement prompt lists the tools of the registry
The implement step SHALL list the tools it offers in a table of its prompt, and SHALL name them from the registry `TOOLS` through `tool_names(HOLDER_IMPLEMENT)` in place of a hand-written set.

#### Scenario: The tools table holds each registry name
- **WHEN** A test builds the prompt of the step with `fill_prompt`.
- **THEN** The table holds each name that `tool_names(HOLDER_IMPLEMENT)` gives, with its read flag and its purpose, and holds no other tool name.

#### Scenario: The step takes its local tool names from the same holder
- **WHEN** A test reads `IMPLEMENT_LOCAL_TOOL_NAMES` of the step.
- **THEN** It holds the six names of the implement holder, and `read_file` and `list_files` are two of them.

## MODIFIED Requirements

### Requirement: The prompt lists the local devops commands of the catalog
The prompt of the step SHALL list each command of `LOCAL_COMMANDS` with its access class and its use, and the workflow document SHALL hold the same table. `LOCAL_COMMANDS` SHALL hold no command with the access `network`. A call of a listed command through `uv run` SHALL pass the shell policy and SHALL NOT count as a refusal. The `ai ast` and `ai repomap` entries SHALL have access `read`, and the use of `ai ast` SHALL name no `--output`.

#### Scenario: The prompt holds the table
- **WHEN** The prompt of the step is built.
- **THEN** It holds the text of `local_commands_table()` and no placeholder.

#### Scenario: The document holds the table
- **WHEN** The workflow document of the step is read.
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

#### Scenario: The command table holds the wanted commands
- **WHEN** A test reads `LOCAL_COMMANDS`.
- **THEN** It holds `ci test`, `ai repomap`, `ai ast`, `docs generate` and `openspec check`, and no command with the access `network`.

#### Scenario: The code-intelligence commands are reads
- **WHEN** A test reads `LOCAL_COMMANDS`.
- **THEN** The `ai ast` and `ai repomap` entries have access `read`, and neither use text names `--output`.
