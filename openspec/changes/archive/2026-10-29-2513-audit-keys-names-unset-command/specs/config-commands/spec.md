## ADDED Requirements

### Requirement: The alert of devops config audit-keys names the commands that remove a leak
The alert for a plaintext secret SHALL name `devops config set <key>`, with `--from-file <path>` for a multi-line credential. It SHALL name `DEVOPS_CLI_CONFIG=<file> devops config unset <key>`, which removes the value from the file of the leak. It SHALL NOT name a value in the argument list.

#### Scenario: A leak in the global config file while a project file is active
- **WHEN** the global config file holds `ai.api_key` with a value, the directory walk finds `.devcontainer/config.yaml` with no secret, and `devops config audit-keys` runs
- **THEN** the alert names both commands, and the command exits 1. A plain `devops config unset ai.api_key` exits 1 and changes nothing. `DEVOPS_CLI_CONFIG=<global config file> devops config unset ai.api_key` exits 0. The next `devops config audit-keys` exits 0 with no leak

#### Scenario: A leak in the config.yaml of the current directory that the settings do not merge
- **WHEN** `config.yaml` in the current directory holds `grafana.token` with a value, `DEVOPS_CLI_CONFIG` names another file with no secret, and `devops config audit-keys` runs
- **THEN** the alert names the same commands. `DEVOPS_CLI_CONFIG=<that config.yaml> devops config unset grafana.token` exits 0. The next `devops config audit-keys` exits 0 with no leak

#### Scenario: A multi-line credential
- **WHEN** the global config file holds `argocd.github_app_private_key` as a PEM block, and a person follows the alert with `--from-file <path>` and then the removal command
- **THEN** the keyring holds the whole PEM text, the removal exits 0, and the next `devops config audit-keys` exits 0

### Requirement: The alert of devops config audit-keys warns about the quotes and the copy
The alert SHALL say to quote the file and the key for the shell. It SHALL say that the removal keeps a copy `<file>.bak-<time>` of the file. It SHALL say that the copy still holds the value, and that a person deletes it by hand.

#### Scenario: The alert for a leak
- **WHEN** the global config file holds `ai.api_key` with a value and `devops config audit-keys` runs
- **THEN** the alert holds "Quote <file> and <key> for the shell." and "Delete the copy by hand."

### Requirement: The alert of devops config audit-keys prints for any name
The audit SHALL print the alert and the line of an unaudited file for any section name, key name or path. A name that is markup for the terminal, such as `[/x]`, SHALL NOT stop the print.

#### Scenario: A section name that is markup
- **WHEN** `config.yaml` in the current directory holds the section `[/x]` with the key `grafana.token` and a value, and `devops config audit-keys` runs
- **THEN** the alert names `[/x].grafana.token`, and the command exits 1

#### Scenario: A directory name that is markup
- **WHEN** `DEVOPS_CLI_CONFIG` names a file that is not valid YAML in the directories `[` and `x]`, and `devops config audit-keys` runs
- **THEN** the line of the unaudited file names the path, and the command exits 1

### Requirement: The help of devops config names the commands that remove a leak
The help of `devops config audit-keys` SHALL name the same commands as its alert. The help of `devops config unset` SHALL say that `DEVOPS_CLI_CONFIG` names the file that the command edits, and that `--from-file <path>` stores a multi-line credential.

#### Scenario: The help names the commands
- **WHEN** `devops config audit-keys --help` and `devops config unset --help` run
- **THEN** the help of `audit-keys` holds `DEVOPS_CLI_CONFIG=<file> devops config unset <key>` and `--from-file <path>`. The help of `unset` says that `DEVOPS_CLI_CONFIG` names the file that the command edits
