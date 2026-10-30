## ADDED Requirements

### Requirement: A caller override of a key that makes uv or npm run a program is refused
`build_subprocess_env` SHALL raise `SecurityError` with the message "Prohibited dangerous environment variable override: '<key>'" and the error code `SECURITY_ERROR` for a caller override of a key that makes uv or npm start a program that the caller names. The scenarios list the keys. It SHALL do this with environment isolation on and off.

#### Scenario: The interpreter and the environment of uv
- **WHEN** a caller builds a child environment with the override `UV_PYTHON`, `UV_PYTHON_INSTALL_DIR`, `UV_PROJECT_ENVIRONMENT` or `VIRTUAL_ENV`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The shell, the options, the git program, the editor and the init module of npm
- **WHEN** a caller builds a child environment with the override `npm_config_script_shell`, `npm_config_node_options`, `npm_config_git`, `npm_config_editor` or `npm_config_init_module`, in any case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The spelling with a hyphen
- **WHEN** a caller builds a child environment with the override `npm_config_script-shell`, `npm_config_node-options` or `npm_config_init-module`, which npm reads as the same setting as the spelling with an underscore
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A refused key starts no child
- **WHEN** a caller runs a program with `run_subprocess` and the override `UV_PYTHON`
- **THEN** `run_subprocess` raises `SecurityError` and the program does not start

### Requirement: An isolated child gets no VIRTUAL_ENV and no npm program key from the environment
With isolation on, `build_subprocess_env` SHALL keep `VIRTUAL_ENV` and each key that the previous requirement refuses for npm out of the child environment, in each spelling and case. With isolation off, the child gets the environment as it is. No key of `DEFAULT_ALLOWED_ENV_VARS` SHALL be `VIRTUAL_ENV`.

#### Scenario: The keys in the environment of the person
- **WHEN** the environment holds `VIRTUAL_ENV` and the npm keys, and a caller builds a child environment with isolation on
- **THEN** the child environment holds none of these keys

#### Scenario: Isolation off
- **WHEN** the environment holds `VIRTUAL_ENV` and `npm_config_script_shell`, and a caller builds a child environment with isolation off
- **THEN** the child environment holds both keys with their values

### Requirement: An isolated child gets the uv settings of the person
With isolation on, `build_subprocess_env` SHALL keep each `UV_` key of the environment that no denied pattern matches, `UV_PYTHON`, `UV_PYTHON_INSTALL_DIR` and `UV_PROJECT_ENVIRONMENT` included, so that a `uv run` of the gate keeps the interpreter and the environment that the runner built.

#### Scenario: The uv settings of a runner
- **WHEN** the environment holds `UV_PYTHON`, `UV_PYTHON_INSTALL_DIR`, `UV_PROJECT_ENVIRONMENT` and `UV_CACHE_DIR`, and a caller builds a child environment with isolation on
- **THEN** the child environment holds each of these keys with its value

### Requirement: A uv or npm key that names no program or that names a file reaches the child
`build_subprocess_env` SHALL put `npm_config_cache`, `npm_config_userconfig`, `npm_config_globalconfig`, `npm_config_update_notifier`, `npm_config_loglevel`, `UV_CACHE_DIR`, `UV_LINK_MODE`, `UV_MALWARE_CHECK`, `UV_CONFIG_FILE` and `UV_PYTHON_DOWNLOADS` of the caller override in the child environment with their values, with isolation on and off. It SHALL do the same for a key that only contains a refused name.

#### Scenario: The settings of the installer and keys that look like a refused key
- **WHEN** a caller builds a child environment with these overrides, `npm_config_git_tag_version`, `EXAMPLE_UV_PYTHON` and `VIRTUAL_ENV_EXAMPLE`
- **THEN** the child environment holds each of these keys with its value

## MODIFIED Requirements

### Requirement: An isolated child gets no refused key from the environment
With environment isolation on, `build_subprocess_env` SHALL keep each key that the caller override refuses out of the child environment when the key is in the environment of the process and the caller names no `extra_allowed_keys`. The one exception is the keys that the prefix `UV_` lets through: `UV_PYTHON`, `UV_PYTHON_INSTALL_DIR` and `UV_PROJECT_ENVIRONMENT`.

#### Scenario: Refused keys in the environment of the person
- **WHEN** the environment holds `PYTHONPATH`, `PYTHONHOME`, `ZDOTDIR`, `NODE_OPTIONS`, `PERL5LIB`, `LD_PRELOAD`, `BASH_ENV` and each other refused key but the three uv keys, and a caller builds a child environment with isolation on
- **THEN** the child environment holds none of these keys
