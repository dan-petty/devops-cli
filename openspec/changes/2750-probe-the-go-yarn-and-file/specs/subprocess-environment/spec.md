## MODIFIED Requirements

### Requirement: A caller override of a key that makes uv or npm run a program is refused
`build_subprocess_env` SHALL raise `SecurityError` with the message "Prohibited dangerous environment variable override: '<key>'" and the error code `SECURITY_ERROR` for a caller override of a key that makes uv or npm start a program that the caller names, and for `UV_ENV_FILE`, which puts refused keys into the program that `uv run` starts. The scenarios list the keys. It SHALL do this with environment isolation on and off.

#### Scenario: The interpreter and the environment of uv
- **WHEN** a caller builds a child environment with the override `UV_PYTHON`, `UV_PYTHON_INSTALL_DIR`, `UV_PROJECT_ENVIRONMENT` or `VIRTUAL_ENV`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The shell, the options, the git program, the editor, the init module and the interpreter of npm
- **WHEN** a caller builds a child environment with the override `npm_config_script_shell`, `npm_config_node_options`, `npm_config_git`, `npm_config_editor`, `npm_config_init_module`, `npm_config_shell`, `npm_config_python` or `PYTHON`, in any case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The spelling with a hyphen
- **WHEN** a caller builds a child environment with the override `npm_config_script-shell`, `npm_config_node-options` or `npm_config_init-module`, which npm reads as the same setting as the spelling with an underscore
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A refused key starts no child
- **WHEN** a caller runs a program with `run_subprocess` and the override `UV_PYTHON`
- **THEN** `run_subprocess` raises `SecurityError` and the program does not start

#### Scenario: The tool directory and the environment file of uv
- **WHEN** a caller builds a child environment with the override `UV_TOOL_DIR` or `UV_ENV_FILE`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

## ADDED Requirements

### Requirement: A caller override of a key that makes go or yarn run a program is refused
`build_subprocess_env` SHALL raise `SecurityError` with the message "Prohibited dangerous environment variable override: '<key>'" and the error code `SECURITY_ERROR` for a caller override whose upper-case key is `GOFLAGS` or `YARN_YARN_PATH`. `GOFLAGS` can carry `-toolexec`, and `YARN_YARN_PATH` names the file that Yarn 4 runs. It SHALL do this with environment isolation on and off.

#### Scenario: The flags of go and the path of Yarn
- **WHEN** a caller builds a child environment with the override `GOFLAGS` or `YARN_YARN_PATH`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A refused key starts no child
- **WHEN** a caller runs a program with `run_subprocess` and the override `GOFLAGS`
- **THEN** `run_subprocess` raises `SecurityError` and the program does not start

#### Scenario: Keys that only contain a refused name
- **WHEN** a caller builds a child environment with the overrides `EXAMPLE_GOFLAGS`, `GOFLAGS_EXAMPLE` and `EXAMPLE_YARN_YARN_PATH`
- **THEN** the child environment holds each of these keys with its value

### Requirement: An isolated child gets no Go, Yarn, UV_TOOL_DIR and UV_ENV_FILE key from the environment
With isolation on, `build_subprocess_env` SHALL keep `GOFLAGS`, `YARN_YARN_PATH`, `UV_TOOL_DIR` and `UV_ENV_FILE` out of the child environment, in upper and lower case, although the prefix `UV_` passes the other uv keys. With isolation off, the child gets the environment as it is.

#### Scenario: The keys in the environment of the person
- **WHEN** the environment holds these four keys and `UV_CACHE_DIR`, and a caller builds a child environment with isolation on
- **THEN** the child environment holds `UV_CACHE_DIR` with its value and none of the four keys

#### Scenario: Isolation off
- **WHEN** the environment holds these four keys, and a caller builds a child environment with isolation off
- **THEN** the child environment holds each of the four keys with its value
