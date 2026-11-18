## ADDED Requirements

### Requirement: Timeout error line
The `devops test run` command SHALL report a pytest subprocess timeout as one `DevOpsCLIError` line and exit with status 1.

#### Scenario: Changed run exceeds timeout
- **WHEN** The pytest subprocess exceeds the test-run timeout.
- **THEN** The command prints one error line that names the timeout in seconds and the `--timeout` option, prints no traceback, and exits 1.

### Requirement: Configurable timeout
The `devops test run` command SHALL use the `--timeout` option, default 1800 seconds, as the pytest subprocess timeout.

#### Scenario: Custom timeout value
- **WHEN** A user runs `devops test run --timeout 60`.
- **THEN** The command passes 60 seconds as the timeout to `run_subprocess`.

### Requirement: Effective timeout in message
The timeout error line SHALL state the effective timeout value that stopped the run.

#### Scenario: Non-default timeout in error
- **WHEN** The test run uses a timeout of 60 seconds and the subprocess exceeds it.
- **THEN** The error line states 60 seconds, not 1800 seconds.

### Requirement: Non-timeout behavior
The command SHALL keep the existing output and exit status for a pytest failure that is not a timeout.

#### Scenario: Pytest fails before timeout
- **WHEN** The pytest subprocess exits with a non-zero status before the timeout.
- **THEN** The command reports the pytest result as before and prints no timeout error.
