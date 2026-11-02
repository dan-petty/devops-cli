## ADDED Requirements

### Requirement: Refuse Go, Yarn and uv file keys
`build_subprocess_env` SHALL raise `SecurityError` when a caller sets `GOFLAGS`, `YARN_YARN_PATH` or `UV_ENV_FILE`.

#### Scenario: Caller sets GOFLAGS
- **WHEN** A caller passes `GOFLAGS` in the env dict
- **THEN** `build_subprocess_env` raises `SecurityError`.

#### Scenario: Caller sets YARN_YARN_PATH
- **WHEN** A caller passes `YARN_YARN_PATH` in the env dict
- **THEN** `build_subprocess_env` raises `SecurityError`.

#### Scenario: Caller sets UV_ENV_FILE
- **WHEN** A caller passes `UV_ENV_FILE` in the env dict
- **THEN** `build_subprocess_env` raises `SecurityError`.
