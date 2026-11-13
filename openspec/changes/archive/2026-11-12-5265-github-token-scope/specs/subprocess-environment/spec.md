## MODIFIED Requirements

### Requirement: A caller override of a git key that devops-cli does not set is refused
`build_subprocess_env` SHALL raise `SecurityError` for a caller override whose upper-case key starts with `GIT_`, but not for the seven keys of the next requirement, nor for `CONST_GIT_ISOLATED_CONFIG_ENV`. It SHALL refuse `EDITOR`, `VISUAL`, `PAGER`, `LESSOPEN`, `LESSCLOSE` and `MERGE_TOOLS_DIR` in the same way. The message is "Prohibited dangerous environment variable override: '<key>'" and the error code is `SECURITY_ERROR`. It SHALL do this with environment isolation on and off.

#### Scenario: A git configuration key
- **WHEN** a caller builds a child environment with the override `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0`, `GIT_CONFIG_VALUE_12`, `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_GLOBAL` or `GIT_CONFIG_SYSTEM` with the value `libexample.so`, in upper or lower case
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
- **WHEN** a caller builds a child environment with the override `GIT_SSH_VARIANT`, `GIT_CONFIG_NOSYSTEM` or `GIT_EXAMPLE_KEY` with the value `libexample.so`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The editor, the pager and their filters
- **WHEN** a caller builds a child environment with the override `EDITOR`, `VISUAL`, `PAGER`, `LESSOPEN` or `LESSCLOSE`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

## ADDED Requirements

### Requirement: The two git keys that turn a configuration file off reach the child with their fixed value
`build_subprocess_env` SHALL put the caller override `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1` in the child environment, with isolation on and off. It SHALL refuse each of the two keys with any other value, and in lower case.

#### Scenario: The fixed values
- **WHEN** a caller builds a child environment with the overrides `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1`
- **THEN** the child environment holds both keys with these values, with isolation on and off

#### Scenario: Another value
- **WHEN** a caller builds a child environment with the override `GIT_CONFIG_GLOBAL=/tmp/example.gitconfig`, `GIT_CONFIG_NOSYSTEM=0` or `git_config_global=/dev/null`
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key

### Requirement: Only a git child that reaches a remote gets the session's token
The process runner SHALL give `GH_TOKEN` set to the session's token only to a git child whose subcommand is in `CONST_GIT_NETWORK_SUBCOMMANDS`, or is `remote` with an action of `CONST_GIT_REMOTE_NETWORK_ACTIONS`. It SHALL read the subcommand after the global options of git, and take the next word as the value of an option of `CONST_GIT_VALUE_OPTIONS`. Any other git child SHALL get no `GH_TOKEN` and no `GITHUB_TOKEN`, and SHALL start no lookup of the token.

#### Scenario: A network command and a local command
- **WHEN** the process runner starts `git push origin feat/184-example`, `git -C /tmp/x fetch origin main` and `git ls-remote --heads origin`, and then `git add -A`, `git -c user.name=x commit -m x` and `git diff --cached`
- **THEN** each of the first three children gets the session's token as `GH_TOKEN`, and each of the last three gets no `GH_TOKEN` and no `GITHUB_TOKEN`

#### Scenario: A local command and no login
- **WHEN** no token resolves and the process runner starts `git status`
- **THEN** the child starts, and no `gh auth token` runs

### Requirement: A gh child reads the session's token from a private configuration folder
The process runner SHALL give a gh child, except a local gh command (`gh auth`, version and help), no `GH_TOKEN` and no `GITHUB_TOKEN`. It SHALL give it a new folder (mode 0700) whose `hosts.yml` (mode 0600) holds the session's token, with `GH_CONFIG_DIR` set to the folder and `GH_HOST` set to `github.com`, and SHALL remove the folder when the child ends, also when the child fails, runs out of time or is cancelled.

#### Scenario: A gh call with a jq filter
- **WHEN** the process runner starts `gh api rate_limit --jq '[env.GH_TOKEN, env.GITHUB_TOKEN]'`, and the child ends with status 0, with status 1, or after its timeout
- **THEN** the environment of the child holds no `GH_TOKEN` and no `GITHUB_TOKEN`, `GH_CONFIG_DIR` names a folder with mode 0700 whose `hosts.yml` has mode 0600 and holds the session's token, `GH_HOST` is `github.com`, and the folder is gone after the run

#### Scenario: The App's installation token
- **WHEN** the process acts as the App and starts a gh child
- **THEN** the `hosts.yml` of the child holds the installation token, and its environment holds no token

### Requirement: The folder of a gh child does not depend on the current folder
The process runner SHALL make the folder of a gh child directly in the runtime folder of the user (`platformdirs`), else directly in the temp folder of the system, else in `<data directory>/gh-config` when the data directory is absolute. A candidate that raises `OSError` SHALL give way to the next. When none works, the call SHALL raise `ConfigurationError` that names the settings.

#### Scenario: Where the folder is
- **WHEN** `XDG_RUNTIME_DIR` names a private folder
- **THEN** the folder of a gh child is directly in `$XDG_RUNTIME_DIR`

#### Scenario: No runtime folder
- **WHEN** the runtime folder cannot hold a folder, as in a runner Job with a read-only root file system, and the process runner starts a gh child
- **THEN** the folder of the child is a new folder with mode 0700 in the temp folder of the system

#### Scenario: Only the data directory
- **WHEN** the runtime folder and the temp folder fail, and the data directory is absolute
- **THEN** the folder of the child is under `<data directory>/gh-config`

#### Scenario: A relative data directory
- **WHEN** the runtime folder and the temp folder fail, the data directory is `.data`, and the current folder cannot be written
- **THEN** the call raises `ConfigurationError` that names `data.dir` and `XDG_RUNTIME_DIR`, the gh child does not start, and the current folder holds nothing new

### Requirement: A candidate folder that is a link or in the current folder is skipped
A runtime folder or a `gh-config` folder that is a link, belongs to another user or that others can read SHALL raise `OSError`. A runtime or temp folder that resolves into the current folder SHALL raise `OSError`, unless the current folder is the root of the file system.

#### Scenario: A link below the runtime folder
- **WHEN** `<runtime folder>/devops-cli` is a link into a checkout
- **THEN** the folder of a gh child is directly in the runtime folder, and not in the checkout

#### Scenario: A runtime or temp folder in the current folder
- **WHEN** the runtime folder or the temp folder resolves into the current folder, and the data directory is absolute
- **THEN** the folder of the child is under `<data directory>/gh-config`, outside the current folder

#### Scenario: The current folder is the root of the file system
- **WHEN** the current folder is `/` and `XDG_RUNTIME_DIR` names a private folder
- **THEN** the folder of a gh child is directly in `$XDG_RUNTIME_DIR`

### Requirement: An async gh call makes its folder after the token lookup
An async call SHALL look up the token in a thread and make the folder of the gh child in the thread of the event loop, so that a cancelled call leaves no folder.

#### Scenario: A cancelled call
- **WHEN** an async gh call is cancelled while it looks up the token
- **THEN** no folder with the token is left after the lookup ends

### Requirement: In a runner, the leftover processes end before and after each child that gets the session's token
When `roadmap.implement.in_runner` is true, the process runner SHALL end every leftover process of the job (`end_leftover_processes`) before it starts a gh child or a git child that gets the session's token, before it makes the token folder of a gh child, and again after the child ends. A process that survives the first sweep SHALL raise `RoadmapImplementError`, and the child SHALL NOT start. A local git child and a local gh command SHALL start no sweep.

#### Scenario: The order
- **WHEN** in a runner the process runner starts `gh api rate_limit`, `git push origin feat/184-example`, `git status` and `gh --version`
- **THEN** the leftover processes end before and after each of the first two children, and before and after neither of the last two

#### Scenario: A process that survives
- **WHEN** in a runner a process survives the sweep before a gh child
- **THEN** the call raises `RoadmapImplementError`, the child does not start, and no `hosts.yml` exists

### Requirement: A child that gets the session's token stops with its process group
The process runner SHALL start each child that gets the session's token in a session of its own. A timeout, or another error while the child runs, SHALL kill the whole process group of the child.

#### Scenario: A timeout
- **WHEN** a git child that reaches a remote starts a helper and runs past its timeout
- **THEN** the call raises `subprocess.TimeoutExpired`, and neither the child nor the helper is alive
