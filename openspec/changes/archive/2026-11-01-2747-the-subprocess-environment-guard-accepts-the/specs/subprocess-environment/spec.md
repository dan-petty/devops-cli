## MODIFIED Requirements

### Requirement: A caller override of a key that makes a child write a file that the caller names is refused
`build_subprocess_env` SHALL raise `SecurityError` with the message "Prohibited dangerous environment variable override: '<key>'" and the error code `SECURITY_ERROR` for a caller override whose upper-case key is `SSLKEYLOGFILE`, `QLOGDIR`, `NODE_V8_COVERAGE`, `NODE_REDIRECT_WARNINGS`, `PYTEST_ADDOPTS`, `NPM_CONFIG_LOGS_DIR`, `NPM_CONFIG_LOGS-DIR` or starts with `LD_`. It SHALL do this with environment isolation on and off.

#### Scenario: The TLS secrets and the QUIC log
- **WHEN** a caller builds a child environment with the override `SSLKEYLOGFILE` or `QLOGDIR`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The coverage data and the warnings of Node.js
- **WHEN** a caller builds a child environment with the override `NODE_V8_COVERAGE` or `NODE_REDIRECT_WARNINGS`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The options of pytest and the log directory of npm
- **WHEN** a caller builds a child environment with the override `PYTEST_ADDOPTS`, `npm_config_logs_dir` or `npm_config_logs-dir`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The debug and profile keys of the glibc loader
- **WHEN** a caller builds a child environment with the override `LD_DEBUG`, `LD_DEBUG_OUTPUT`, `LD_PROFILE`, `LD_PROFILE_OUTPUT` or another key that starts with `LD_`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A refused key starts no child
- **WHEN** a caller runs a program with `run_subprocess` and the override `SSLKEYLOGFILE`
- **THEN** `run_subprocess` raises `SecurityError` and the program does not start

### Requirement: An isolated child gets no file-write key from the environment
With isolation on, `build_subprocess_env` SHALL keep `SSLKEYLOGFILE`, `QLOGDIR`, `NODE_V8_COVERAGE`, `NODE_REDIRECT_WARNINGS`, `PYTEST_ADDOPTS`, `npm_config_logs_dir`, `npm_config_logs-dir` and each key that starts with `LD_` out of the child environment, in upper and lower case. With isolation off, the child gets the environment as it is.

#### Scenario: The keys in the environment of the person
- **WHEN** the environment holds one of these keys, and a caller builds a child environment with isolation on
- **THEN** the child environment holds none of these keys

#### Scenario: Isolation off
- **WHEN** the environment holds `SSLKEYLOGFILE` and `LD_DEBUG`, and a caller builds a child environment with isolation off
- **THEN** the child environment holds both keys with their values

### Requirement: A key that only contains a refused name reaches the child
`build_subprocess_env` SHALL put a key of the caller override in the child environment with its value when the key only contains a refused file-write name, or contains `LD_` after its first characters, with isolation on and off. `SSL_CERT_FILE` and `NODE_EXTRA_CA_CERTS` are examples of keys that write no file. `npm_config_cache` also makes npm write files and stays accepted, because `devops install-tools` sets it.

#### Scenario: Keys with a similar name
- **WHEN** a caller builds a child environment with the overrides `SSL_CERT_FILE`, `NODE_EXTRA_CA_CERTS`, `EXAMPLE_SSLKEYLOGFILE`, `QLOGDIR_EXAMPLE`, `BUILD_ID`, `OLD_LD_EXAMPLE`, `EXAMPLE_PYTEST_ADDOPTS` and `npm_config_logs_dirs`
- **THEN** the child environment holds each of these keys with its value
