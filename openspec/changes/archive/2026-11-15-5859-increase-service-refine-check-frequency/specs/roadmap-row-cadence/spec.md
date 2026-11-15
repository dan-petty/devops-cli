## MODIFIED Requirements

### Requirement: Each row reads its interval from its settings at each round
The rows `intake`, `stage`, `fix_plan`, `refine` and `alternatives` SHALL be due by the interval of `roadmap.<row>.interval_minutes`, which a round SHALL read from the settings at its start. The defaults SHALL be 29, 37, 53, 7 and 239 minutes. The section `roadmap.refine` SHALL hold the settings of the refine row. A variable SHALL set each setting, such as `DEVOPS_CLI_ROADMAP_STAGE_INTERVAL_MINUTES`. A setting below 1 SHALL stop the settings from loading.

#### Scenario: The defaults are the old intervals
- **WHEN** A test loads the settings with no source that sets a cadence.
- **THEN** `interval_minutes` is 29 for intake, 37 for stage, 53 for fix_plan, 7 for refine and 239 for alternatives, and `backlog_interval_minutes` and `backlog_threshold` are empty in each section.

#### Scenario: A variable changes the interval of the next round
- **WHEN** A test sets `DEVOPS_CLI_ROADMAP_STAGE_INTERVAL_MINUTES` to 20 and runs a dry round 20 minutes and 19 minutes after the last success of stage.
- **THEN** The round at 20 minutes lists stage, and the round at 19 minutes does not.
