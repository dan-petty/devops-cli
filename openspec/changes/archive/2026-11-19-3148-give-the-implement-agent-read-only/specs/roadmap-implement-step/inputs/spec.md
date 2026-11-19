## ADDED Requirements

### Requirement: The implement prompt lists the tools of the registry
The implement step SHALL list the tools it offers in a table of its prompt, and SHALL name them from the registry `TOOLS` through `tool_names(HOLDER_IMPLEMENT)` in place of a hand-written set.

#### Scenario: The tools table holds each registry name
- **WHEN** A test builds the prompt of the step with `fill_prompt`.
- **THEN** The table holds each name that `tool_names(HOLDER_IMPLEMENT)` gives, with its read flag and its purpose, and holds no other tool name.

#### Scenario: The step takes its local tool names from the same holder
- **WHEN** A test reads `IMPLEMENT_LOCAL_TOOL_NAMES` of the step.
- **THEN** It holds the six names of the implement holder, and `read_file` and `list_files` are two of them.

### Requirement: The code-intelligence commands of the catalog are read-only
The `ai ast` and `ai repomap` entries of `LOCAL_COMMANDS` SHALL have access `read`, and the use of `ai ast` SHALL name no `--output`.

#### Scenario: The command table holds the wanted commands
- **WHEN** A test reads `LOCAL_COMMANDS`.
- **THEN** It holds `ci test`, `ai repomap`, `ai ast`, `docs generate` and `openspec check`, and no command with the access `network`.

#### Scenario: The code-intelligence commands are reads
- **WHEN** A test reads `LOCAL_COMMANDS`.
- **THEN** The `ai ast` and `ai repomap` entries have access `read`, and neither use text names `--output`.
