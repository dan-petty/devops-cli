# devcontainer-keyring-unlock Specification

## Purpose
How `devops devcontainer unlock-keyring` handles password verification and provides actionable remediation when an existing keyring rejects the password.

## Requirements

### Requirement: Keyring wrong password error provides clear remediation
When `devops devcontainer unlock-keyring` runs against an existing keyring file and `gnome-keyring-daemon` fails to unlock it, the command SHALL exit with status 1. The output SHALL print an error message that states the keyring is locked, names the keyring file path, and specifies the command to move the file to a backup and rerun `devops devcontainer unlock-keyring`.

#### Scenario: Wrong password entered for existing keyring
- **WHEN** an existing keyring file exists at `~/.local/share/keyrings/login.keyring`
- **AND** the entered password does not unlock the keyring
- **THEN** the command exits 1
- **AND** the error output names the keyring file path
- **AND** the error output contains the instruction to move the file to a backup and run `devops devcontainer unlock-keyring`
