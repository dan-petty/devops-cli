# config-commands Specification

## Purpose
What the `devops config` commands tell the user about the config file that they read and write.

## Requirements

### Requirement: devops config init names the file that it writes
When `devops config init` saves the settings, its `Config file:` line SHALL name the file that the wizard wrote, which is the active config path.

#### Scenario: DEVOPS_CLI_CONFIG names a different file
- **WHEN** `DEVOPS_CLI_CONFIG` names a file that is not the default config path, and the user completes `devops config init`
- **THEN** the wizard writes the new values to that file, and its `Config file:` line names that file
