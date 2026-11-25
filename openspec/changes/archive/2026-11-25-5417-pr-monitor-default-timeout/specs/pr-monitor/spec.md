## ADDED Requirements

### Requirement: Named default timeout
The project SHALL define `DEFAULT_PR_MONITOR_TIMEOUT_SECONDS` as `600` in `src/devops_cli/config/defaults.py`.

#### Scenario: Constant holds 600 seconds
- **WHEN** a unit test imports `DEFAULT_PR_MONITOR_TIMEOUT_SECONDS` from `devops_cli.config.defaults`
- **THEN** the value equals `600`

### Requirement: Monitor uses the default timeout
`monitor_pr_command`, `monitor_pr`, and `plan_pr_monitor` SHALL use `DEFAULT_PR_MONITOR_TIMEOUT_SECONDS` (`600`) as the default of `timeout` / `--timeout`.

#### Scenario: Command default matches the constant
- **WHEN** a unit test inspects the default of the `timeout` parameter of `monitor_pr_command`
- **THEN** the default equals `DEFAULT_PR_MONITOR_TIMEOUT_SECONDS` (`600`)

### Requirement: Explicit timeout override
`devops pr monitor` SHALL keep an explicit `--timeout` value instead of the default.

#### Scenario: Explicit timeout is kept
- **WHEN** a test builds or runs the dry-run plan of `devops pr monitor 42 -R owner/repo --timeout 42 --dry-run`
- **THEN** the planned monitor request reports `up to 42s` instead of `600s`
