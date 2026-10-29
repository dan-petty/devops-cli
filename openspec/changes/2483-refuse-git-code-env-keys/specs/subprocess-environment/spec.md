## ADDED Requirements

### Requirement: A caller override that makes git run a program is refused
`build_subprocess_env` SHALL raise `SecurityError` with the message "Prohibited dangerous environment variable override: '<key>'" and the error code `SECURITY_ERROR` when the upper-case form of a key of the caller override is a git key that a scenario of this requirement names, or starts with `GIT_CONFIG_KEY_` or `GIT_CONFIG_VALUE_`. It SHALL do this with environment isolation on and off.

#### Scenario: A git configuration value
- **WHEN** a caller builds a child environment with the override `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0`, `GIT_CONFIG_VALUE_0`, `GIT_CONFIG_KEY_12`, `GIT_CONFIG_VALUE_12` or `GIT_CONFIG_PARAMETERS`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A git configuration file
- **WHEN** a caller builds a child environment with the override `GIT_CONFIG_GLOBAL` or `GIT_CONFIG_SYSTEM`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A program that git starts
- **WHEN** a caller builds a child environment with the override `GIT_SSH`, `GIT_SSH_COMMAND`, `GIT_ASKPASS`, `GIT_EDITOR`, `GIT_SEQUENCE_EDITOR`, `GIT_PAGER`, `GIT_EXTERNAL_DIFF` or `GIT_PROXY_COMMAND`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A directory of git programs or hooks
- **WHEN** a caller builds a child environment with the override `GIT_EXEC_PATH` or `GIT_TEMPLATE_DIR`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The editor and the pager that git falls back to
- **WHEN** a caller builds a child environment with the override `EDITOR`, `VISUAL` or `PAGER`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

### Requirement: A git key that runs no program reaches the child
`build_subprocess_env` SHALL put each git key of the caller override that runs no program in the child environment with its value, and each key that contains a refused git name but does not start with it.

#### Scenario: Git keys that run no program and keys that look like a refused key
- **WHEN** a caller builds a child environment with the overrides `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL`, `GIT_TERMINAL_PROMPT`, `GIT_CONFIG_NOSYSTEM`, `GIT_SSH_VARIANT`, `GIT_CONFIGURATION` and `EXAMPLE_GIT_SSH_COMMAND`
- **THEN** the child environment holds each of these keys with its value, with isolation on and off

### Requirement: The fetch of an Argo CD revision never asks a question
`render_at_revision` SHALL run `git fetch` with the argument `-c` and the value `core.sshCommand=ssh -o BatchMode=yes`, and it SHALL give each command the environment override `GIT_TERMINAL_PROMPT=0` and no other git key. The override passes the guard, so the fetch of an SSH remote starts `ssh` with `-o BatchMode=yes`.

#### Scenario: A fetch over SSH through the production runner
- **WHEN** `render_at_revision` fetches the SSH remote `ssh://git@example.com/repository.git` through `_run_cmd`, and a stand-in `ssh` program is first on `PATH`
- **THEN** the stand-in `ssh` starts with the arguments `-o BatchMode=yes`
- **AND** no `SecurityError` is raised before the fetch fails

### Requirement: A git command that writes the global configuration uses the file that the environment names
The calls `git config --global` of `devops ssh register`, `devops ssh rotate` and `devops devcontainer post-start` SHALL name `GIT_CONFIG_GLOBAL` in `extra_allowed_env`. When the environment of the process holds `GIT_CONFIG_GLOBAL`, each call writes its setting in the file that the key names, as `git config --global` does in a shell.

#### Scenario: The signing key of a registered SSH key
- **WHEN** the environment holds `GIT_CONFIG_GLOBAL` with the path of a file below a temporary directory, and `devops ssh register` runs
- **THEN** that file holds `gpg.format`, `user.signingkey` and `commit.gpgsign`

#### Scenario: The git defaults of the post-start step
- **WHEN** the environment holds `GIT_CONFIG_GLOBAL` with the path of a file below a temporary directory, and `devops devcontainer post-start` runs
- **THEN** that file holds `push.autoSetupRemote` set to `true` and `init.defaultBranch` set to `main`
- **AND** the home directory holds no `.gitconfig`
