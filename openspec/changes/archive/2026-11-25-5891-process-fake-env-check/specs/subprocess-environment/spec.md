## ADDED Requirements

### Requirement: Sync run refuses denied environment
`ProcessFake.run` SHALL call `build_subprocess_env` with the call's `env`, `isolate_env`, and `extra_allowed_env` before it returns an answer.

#### Scenario: Denied key fails a sync run
- **WHEN** a test calls `process_fake.run(["cmd"], env={"PYTEST_ADDOPTS": "-n 2"})`
- **THEN** `SecurityError` is raised with the message `"Prohibited dangerous environment variable override: 'PYTEST_ADDOPTS'"`

### Requirement: Async run refuses denied environment
`ProcessFake.run_async` SHALL call `build_subprocess_env` with the call's `env`, `isolate_env`, and `extra_allowed_env` before it returns an answer.

#### Scenario: Denied key fails an async run
- **WHEN** a test awaits `process_fake.run_async(["cmd"], env={"PYTEST_ADDOPTS": "-n 2"})`
- **THEN** `SecurityError` is raised with the message `"Prohibited dangerous environment variable override: 'PYTEST_ADDOPTS'"`

### Requirement: Detached spawn refuses denied environment
`ProcessFake.spawn_detached` SHALL accept an optional `env` mapping and call `build_subprocess_env` with it, `isolate_env`, and `extra_allowed_env` before it returns a child.

#### Scenario: Denied key fails a detached spawn
- **WHEN** a test calls `process_fake.spawn_detached(["cmd"], env={"PYTEST_ADDOPTS": "-n 2"})`
- **THEN** `SecurityError` is raised with the message `"Prohibited dangerous environment variable override: 'PYTEST_ADDOPTS'"`

### Requirement: Environment flags reach the check
`ProcessFake.run`, `run_async`, and `spawn_detached` SHALL pass `isolate_env` and `extra_allowed_env` to `build_subprocess_env` and record them on `ProcessCall`.

#### Scenario: Flags are forwarded
- **WHEN** a test calls each entry point with `isolate_env=False` and `extra_allowed_env={"FOO"}` and spies on `build_subprocess_env`
- **THEN** each spy call receives `isolate_env` false and `extra_allowed_keys` containing `FOO`, and each recorded call holds the same flags

### Requirement: Allowed environment still returns the answer
`ProcessFake.run` SHALL keep the scripted answer when the environment passes the check.

#### Scenario: Allowed env passes
- **WHEN** a test calls `process_fake.run(["cmd"], env={"PATH": "/usr/bin"})` after scripting a zero exit
- **THEN** the call returns the scripted `CompletedProcess` with returncode 0 and records the caller `env`
