## ADDED Requirements

### Requirement: A caller override of a git key that devops-cli does not set is refused
`build_subprocess_env` SHALL raise `SecurityError` for a caller override whose upper-case key starts with `GIT_`, but not for the five keys of the next requirement. It SHALL refuse `EDITOR`, `VISUAL`, `PAGER`, `LESSOPEN`, `LESSCLOSE` and `MERGE_TOOLS_DIR` in the same way. The message is "Prohibited dangerous environment variable override: '<key>'" and the error code is `SECURITY_ERROR`. It SHALL do this with environment isolation on and off.

#### Scenario: A git configuration key
- **WHEN** a caller builds a child environment with the override `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0`, `GIT_CONFIG_VALUE_12`, `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_GLOBAL` or `GIT_CONFIG_SYSTEM`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A program that git starts
- **WHEN** a caller builds a child environment with the override `GIT_SSH`, `GIT_SSH_COMMAND`, `GIT_ASKPASS`, `GIT_EDITOR`, `GIT_SEQUENCE_EDITOR`, `GIT_PAGER`, `GIT_EXTERNAL_DIFF` or `GIT_PROXY_COMMAND`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A directory of git programs or hooks, and the ext transport
- **WHEN** a caller builds a child environment with the override `GIT_EXEC_PATH`, `GIT_TEMPLATE_DIR` or `GIT_ALLOW_PROTOCOL`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A key that the source or a script of git reads
- **WHEN** a caller builds a child environment with the override `GIT_TEST_FSMONITOR`, `GIT_TEST_MAINT_SCHEDULER`, `GIT_DIFFTOOL_EXTCMD` or `MERGE_TOOLS_DIR`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A trace key that writes a file
- **WHEN** a caller builds a child environment with the override `GIT_TRACE`, `GIT_TRACE2` or `GIT_TRACE_CURL`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A git key that no caller sets
- **WHEN** a caller builds a child environment with the override `GIT_SSH_VARIANT`, `GIT_CONFIG_NOSYSTEM` or `GIT_EXAMPLE_KEY`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The editor, the pager and their filters
- **WHEN** a caller builds a child environment with the override `EDITOR`, `VISUAL`, `PAGER`, `LESSOPEN` or `LESSCLOSE`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

### Requirement: A git key that devops-cli sets reaches the child
`build_subprocess_env` SHALL put `GIT_TERMINAL_PROMPT`, `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` and `GIT_COMMITTER_EMAIL` of the caller override in the child environment with their values. It SHALL do the same for a key that only contains a refused git name, and for `XDG_CONFIG_HOME`.

#### Scenario: The five git keys and keys that look like a refused key
- **WHEN** a caller builds a child environment with the overrides `GIT_TERMINAL_PROMPT`, `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL`, `GITHUB_STEP_SUMMARY`, `EXAMPLE_GIT_SSH_COMMAND` and `XDG_CONFIG_HOME`
- **THEN** the child environment holds each of these keys with its value, with isolation on and off

### Requirement: The ambient allowlist holds no refused key
No key of `DEFAULT_ALLOWED_ENV_VARS` SHALL be a key that `build_subprocess_env` refuses from a caller.

#### Scenario: Each allowed key as an override
- **WHEN** a caller builds a child environment with one key of `DEFAULT_ALLOWED_ENV_VARS` as the override
- **THEN** `build_subprocess_env` raises no error, and the child environment holds the key with its value

### Requirement: The fetch of an Argo CD revision never asks a question
`render_at_revision` SHALL run `git fetch` with the argument `-c` and the value `core.sshCommand=ssh -o BatchMode=yes`. It SHALL give each command the environment override `GIT_TERMINAL_PROMPT=0` and no other git key. The override passes the guard, so the fetch of an SSH remote starts `ssh` with `-o BatchMode=yes`.

#### Scenario: A fetch over SSH through run_subprocess
- **WHEN** `render_at_revision` fetches the SSH remote `ssh://git@example.com/repository.git` through `run_subprocess`, and a stand-in `ssh` program is first on `PATH`
- **THEN** the stand-in `ssh` starts with the arguments `-o BatchMode=yes`
- **AND** no `SecurityError` is raised before the fetch fails

### Requirement: A git command that writes the global configuration uses the file that the environment names
The calls `git config --global` of `devops ssh register`, `devops ssh rotate` and `devops devcontainer post-start` SHALL name `GIT_CONFIG_GLOBAL` in `extra_allowed_env`. When the environment holds the key, each call writes in the file that the key names, as `git config --global` does in a shell.

#### Scenario: The signing key of a registered SSH key
- **WHEN** the environment holds `GIT_CONFIG_GLOBAL` with the path of a file below a temporary directory, and `devops ssh register` runs
- **THEN** that file holds `gpg.format`, `user.signingkey` and `commit.gpgsign`

#### Scenario: The git defaults of the post-start step
- **WHEN** the environment holds `GIT_CONFIG_GLOBAL` with the path of a file below a temporary directory, and `devops devcontainer post-start` runs
- **THEN** that file holds `push.autoSetupRemote` set to `true` and `init.defaultBranch` set to `main`
- **AND** the home directory holds no `.gitconfig`
