# devcontainer-keyring-unlock Specification

## Purpose
How `devops devcontainer unlock-keyring` handles password verification and provides actionable remediation when an existing keyring rejects the password.

## Requirements

### Requirement: Keyring wrong password error provides clear remediation
When `devops devcontainer unlock-keyring` runs against an existing keyring file and `gnome-keyring-daemon` fails to unlock it, the command SHALL exit with status 1. The output SHALL print an error message that states the keyring is locked, names the keyring file path, names the backup folder with the copies from earlier unlocks and tells to copy one over the keyring file, and specifies the command to move the file to a backup and rerun `devops devcontainer unlock-keyring`.

#### Scenario: Wrong password entered for existing keyring
- **WHEN** an existing keyring file exists at `~/.local/share/keyrings/login.keyring`
- **AND** the entered password does not unlock the keyring
- **THEN** the command exits 1
- **AND** the error output names the keyring file path
- **AND** the error output names the backup folder `~/.local/share/keyrings/backups`
- **AND** the error output contains the instruction to move the file to a backup and run `devops devcontainer unlock-keyring`

### Requirement: The keyring daemon and its bus get no display
`devops devcontainer post-start` SHALL start the D-Bus session bus, and `devops devcontainer unlock-keyring` SHALL start `gnome-keyring-daemon`, with an environment that holds neither `DISPLAY` nor `WAYLAND_DISPLAY`, also when the container environment sets them. Without a display, gnome-keyring cannot open its GUI unlock prompt, and only that prompt changes the login keyring password to the last password that `--unlock` rejected.

#### Scenario: The session bus starts without a display
- **WHEN** the container environment sets `DISPLAY` and `WAYLAND_DISPLAY`
- **AND** post-start starts the session bus
- **THEN** the environment of `dbus-daemon` holds neither variable

#### Scenario: The unlock daemon starts without a display
- **WHEN** the container environment sets `DISPLAY` and `WAYLAND_DISPLAY`
- **AND** `devops devcontainer unlock-keyring` starts `gnome-keyring-daemon --replace --unlock`
- **THEN** the environment of the daemon holds neither variable

### Requirement: post-start does not ask for the keyring password
`devops devcontainer post-start` SHALL NOT ask for the keyring password, also when its standard input is a terminal and the keyring is waiting to be unlocked. It SHALL keep the pending marker, so that the first interactive terminal asks.

#### Scenario: A terminal is attached to post-start
- **WHEN** post-start runs with a terminal on standard input
- **AND** the pending marker exists
- **THEN** post-start does not start an unlock
- **AND** the pending marker still exists

### Requirement: A successful unlock keeps a copy of the keyring file
After `devops devcontainer unlock-keyring` unlocks an existing keyring, it SHALL copy `login.keyring` to `backups/login.keyring.<UTC YYYYMMDD-HHMMSS>` in the keyring folder, with mode 0600 in a folder with mode 0700, and print the path of the copy. It SHALL make no copy when the file is equal to the newest copy, and no copy after a wrong password. It SHALL keep only the newest `CONST_KEYRING_BACKUP_COUNT` copies. A copy that fails SHALL give a warning and SHALL NOT fail the unlock.

#### Scenario: The first copy
- **WHEN** the password unlocks an existing keyring
- **THEN** the backup folder holds one copy equal to `login.keyring`
- **AND** the copy has mode 0600 and the folder has mode 0700
- **AND** the output names the path of the copy

#### Scenario: An unchanged keyring
- **WHEN** the newest copy is equal to `login.keyring`
- **AND** the password unlocks the keyring
- **THEN** the backup folder holds the same copies as before

#### Scenario: The oldest copy goes
- **WHEN** the backup folder holds `CONST_KEYRING_BACKUP_COUNT` copies
- **AND** the password unlocks a keyring that differs from the newest copy
- **THEN** the folder holds `CONST_KEYRING_BACKUP_COUNT` copies
- **AND** the oldest copy is gone and the newest copy is equal to `login.keyring`

#### Scenario: A wrong password
- **WHEN** the password does not unlock the keyring
- **THEN** the backup folder holds no copy

#### Scenario: A copy that fails
- **WHEN** the password unlocks the keyring
- **AND** the copy cannot be written
- **THEN** the command exits 0
- **AND** the output gives a warning with the cause
