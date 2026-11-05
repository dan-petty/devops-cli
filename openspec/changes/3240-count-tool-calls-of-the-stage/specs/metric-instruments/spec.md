## ADDED Requirements

### Requirement: The tool-call instruments are declared and documented
`INSTRUMENTS` SHALL hold `devops_cli_roadmap_tool_calls_total` and `devops_cli_roadmap_tool_limit_hits_total` as counters with the unit `1`, `devops_cli_roadmap_tool_answer_chars` as a histogram with the unit `{char}`, and `devops_cli_roadmap_tool_calls_per_run` as a histogram with the unit `{call}`. `docs/TELEMETRY.md` SHALL list each one with its kind and its unit.

#### Scenario: The registry and the document list the four instruments
- **WHEN** a test reads `INSTRUMENTS` and `docs/TELEMETRY.md`
- **THEN** both list the four names with the same kind and the same unit

### Requirement: No instrument attribute is named job or instance
The resource of a process sets the Prometheus labels `job` and `instance`, and a data point attribute with either name is lost. So no `emit()` call SHALL send an attribute named `job` or `instance`. The instrument check SHALL name the file and line of each call that does.

#### Scenario: The source tree keeps the rule
- **WHEN** the instrument check reads every module under `src/devops_cli/`
- **THEN** it finds no `emit()` call with the attribute `job` or `instance`

#### Scenario: A module sends the attribute job
- **WHEN** a module calls `emit(COMMAND_TOTAL, 1.0, {"job": "stage"})`
- **THEN** the instrument check names that call, and it passes `emit(COMMAND_TOTAL, 1.0, {"row": "stage"})`
