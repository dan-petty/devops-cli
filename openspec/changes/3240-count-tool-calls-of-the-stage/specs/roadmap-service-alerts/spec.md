## ADDED Requirements

### Requirement: The planner tools have their own alert group
The rule group `roadmap-service-tools` in `k8s/monitoring/prometheus-values.yaml`, apart from the other groups of the Service, SHALL hold the warning alert `RoadmapServiceToolUnused`. Each `devops_cli_` selector of the group SHALL have `job="roadmap-service"`. Its description SHALL end with `(k8s/README.md, Roadmap service)`, and that section SHALL name the alert. promtool SHALL accept the rule.

#### Scenario: The selectors of the group
- **WHEN** a test reads the selectors of the group
- **THEN** each `devops_cli_` selector has `job="roadmap-service"`

#### Scenario: The README section
- **WHEN** a test reads the description of the alert and "Roadmap service" in `k8s/README.md`
- **THEN** the description points to the section, and the section names the alert

### Requirement: A tool that no run called in 7 days warns
`RoadmapServiceToolUnused` SHALL fire, by `row`, `tool` and `toolset`, when the count of calls of the tool in 7 days is 0 and the Service made plan runs of the same `row` and `toolset` in the same 7 days. The count of calls SHALL add the first value of a series that starts in the 7 days. The summary SHALL name the tool and the toolset.

#### Scenario: A tool is not called while runs happen
- **WHEN** `promtool test rules` evaluates a counter that stays at 0 for `repo_map`, a counter that grows for `read_file`, and a histogram of calls per run that grows, all of the same `toolset`
- **THEN** the alert fires for `repo_map` and not for `read_file`

#### Scenario: No run happened
- **WHEN** `promtool test rules` evaluates a counter that stays at 0 for one tool and a histogram of calls per run that does not grow
- **THEN** the alert stays quiet

#### Scenario: A series that starts in the window
- **WHEN** `promtool test rules` evaluates a counter whose first value is 3, 10 hours before the evaluation, and a histogram that grows
- **THEN** the alert stays quiet for that tool

#### Scenario: A tool of another toolset
- **WHEN** `promtool test rules` evaluates a counter at 0 for a tool of the toolset `extended`, and runs of the toolset `base` only
- **THEN** the alert stays quiet for that tool

#### Scenario: A series of another job
- **WHEN** `promtool test rules` evaluates the same series with `job="devops-cli"`
- **THEN** the alert stays quiet
