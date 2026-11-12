## ADDED Requirements

### Requirement: Each usage error leaves one record of its kind and names
The root group of the CLI SHALL record each usage error, also of a help query, a dry run and an MCP tool call, as one line of `usage-errors.jsonl` under the user data root, one `cli_usage_error` log record and one point of `devops_cli_usage_error_total`. The record SHALL hold the kind, the command path below `devops`, the typed name, Click's suggestion, the caller, the agent tool and the version.

#### Scenario: An unknown command word
- **WHEN** a person runs `devops gh prr list`
- **THEN** the ledger has one line with the kind `unknown_command`, the command path `gh`, the name `prr` and the suggestion `pr`

#### Scenario: An unknown option
- **WHEN** a person runs `devops pr view 1 --repoo`
- **THEN** the ledger has one line with the kind `unknown_option`, the command path `pr view`, the name `--repoo` and the suggestion `--repo`

#### Scenario: A help query and a dry run
- **WHEN** a person runs `devops gh prr --help` or `devops --dry-run gh prr list`
- **THEN** the ledger has one line with the kind `unknown_command`

#### Scenario: An MCP tool call
- **WHEN** the MCP dispatcher runs `devops gh prr list`
- **THEN** the ledger line has the caller `mcp`

### Requirement: A usage-error record holds no argument value
A usage-error record SHALL hold names only. A word that is not in the form of a CLI name SHALL be recorded as `<value>`. No ledger line, log record or counter label SHALL hold the message of the error, an argument value or the command line. The counter SHALL have the labels `kind`, `command_path` and `caller` only.

#### Scenario: A token in the place of a command word
- **WHEN** a person runs `devops gh <token> list`
- **THEN** the ledger line has the name `<value>`
- **AND** no ledger line, log record or counter label holds the token

#### Scenario: A value of an option that is not a number
- **WHEN** a person runs `devops pr list --limit <value>`
- **THEN** the ledger line has the kind `bad_value` and the name `limit`
- **AND** no sink holds `<value>`

### Requirement: The record does not change the error that the caller sees
A command that stops on a usage error SHALL show the same error box of Typer and exit with code 2, with no text of the record. When the ledger cannot be written, the command SHALL show one warning and still exit with code 2. The setting `telemetry.usage_ledger` set to false SHALL stop the ledger.

#### Scenario: The error box stays the same
- **WHEN** a person runs `devops gh prr list`
- **THEN** the output is the error box of Typer that names `pr`, and the exit code is 2

#### Scenario: The ledger cannot be written
- **WHEN** the user data root is a file and a person runs `devops gh prr list`
- **THEN** the output holds one warning about the ledger, and the exit code is 2

### Requirement: The environment names the caller of a usage error
The caller of a usage-error record SHALL be `mcp` for an MCP tool call, else `agent` when `detect_agent` finds an agent marker such as `AI_AGENT`, else `ci` when `CI` or `GITHUB_ACTIONS` is set, else `person`. The agent tool SHALL come from the agent name, and the implement job SHALL set `AI_AGENT=devops-implement`.

#### Scenario: An agent runs the command
- **WHEN** `AI_AGENT` is `claude-code_2-1-322_agent` and the command stops on a usage error
- **THEN** the ledger line has the caller `agent` and the agent tool `claude_code`

#### Scenario: A person runs the command
- **WHEN** no agent, CI or MCP marker is set
- **THEN** the ledger line has the caller `person` and no agent tool
