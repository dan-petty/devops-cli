## ADDED Requirements

### Requirement: The git configuration keys of the environment reach only a child of a person
`build_subprocess_env` SHALL give each child the `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_<n>` and `GIT_CONFIG_VALUE_<n>` of the environment of the process when the process does not act as the GitHub App, as a shell gives them, so git reads the credential helper that the devcontainer sets with them. When the process acts as the GitHub App, `build_subprocess_env` MUST give a child none of these keys, with isolation on or off. A caller override of these keys stays refused.

#### Scenario: A git child of a person
- **WHEN** the environment holds the `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_<n>` and `GIT_CONFIG_VALUE_<n>` that set the helper `gh auth git-credential` for github.com, the process does not act as the GitHub App, and a test runs `git -C clone ls-remote --heads origin` through the process runner
- **THEN** the child environment holds these keys with their values, the child gets the session's token as `GH_TOKEN`, and its arguments are the arguments of the caller with no `-c` value

#### Scenario: A git child of the GitHub App
- **WHEN** the environment holds the same keys and the private key of the GitHub App, and a test runs the same command through the process runner
- **THEN** the child environment holds none of these keys, and the child gets the session's token as `GH_TOKEN`

#### Scenario: The GitHub App with isolation off
- **WHEN** the environment holds the same keys and the private key of the GitHub App, and a caller builds a child environment with isolation off
- **THEN** the child environment holds none of these keys

## MODIFIED Requirements

### Requirement: An isolated child gets no refused key from the environment
With environment isolation on, `build_subprocess_env` SHALL keep each key that the caller override refuses out of the child environment when the key is in the environment of the process and the caller names no `extra_allowed_keys`. The exceptions are the keys that the prefix `UV_` lets through, `UV_PYTHON` and `UV_PYTHON_INSTALL_DIR`, and, for a process that does not act as the GitHub App, the upper-case `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_<n>` and `GIT_CONFIG_VALUE_<n>`.

#### Scenario: Refused keys in the environment of the person
- **WHEN** the environment holds `PYTHONPATH`, `PYTHONHOME`, `ZDOTDIR`, `NODE_OPTIONS`, `PERL5LIB`, `LD_PRELOAD`, `BASH_ENV` and each other refused key but the two uv keys, in upper and in lower case, and a caller builds a child environment with isolation on
- **THEN** the child environment holds none of these keys but the upper-case `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0`, `GIT_CONFIG_KEY_12`, `GIT_CONFIG_VALUE_0` and `GIT_CONFIG_VALUE_12`

### Requirement: A git child that reaches no remote gets no credential helper
The process runner MUST NOT add a `-c` value to the arguments of a git child, and MUST NOT give a GitHub token to a git child that reaches no remote.

#### Scenario: A local status
- **WHEN** a test runs `git status` through the process runner with `GH_TOKEN` in the environment of the process
- **THEN** the recorded arguments hold no `-c` credential value, and the environment of the child holds no `GH_TOKEN`.

## REMOVED Requirements

### Requirement: A git child that reaches a remote gets the GitHub credential helper
**Reason**: git finds the credential helper as it does in a shell: the devcontainer sets it with the `GIT_CONFIG_*` keys of the environment, which now reach a child of a person, and the runner and Service images set it in `/etc/gitconfig` (#6653).
**Migration**: The requirement "The git configuration keys of the environment reach only a child of a person" gives a git child the helper of the devcontainer. The network git calls of the implement job keep the values in `CONST_GIT_TOKEN_CALL_CONFIG`, because they read no configuration file.
