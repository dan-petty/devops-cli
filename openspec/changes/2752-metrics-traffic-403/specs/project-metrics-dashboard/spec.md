## ADDED Requirements

### Requirement: The Service collects no repository traffic
A process that acts as the GitHub App SHALL send no request to the four repository traffic endpoints (`traffic/views`, `traffic/clones`, `traffic/popular/referrers` and `traffic/popular/paths`) when it collects the project metrics, and the report SHALL have `traffic_collected` false. A process that acts as a person SHALL send the four requests, and the report SHALL have `traffic_collected` true.

#### Scenario: A run from a workstation
- **WHEN** `get_repository_traffic_metrics` runs in a process that does not act as the App
- **THEN** it sends one request to each of the four traffic paths and the report has `traffic_collected` true

#### Scenario: A collection under the App
- **WHEN** `get_repository_traffic_metrics` runs in a process that acts as the GitHub App, and GitHub is faked at the `gh` edge
- **THEN** no request goes to a path that starts with `repos/<repo>/traffic/` and the report has `traffic_collected` false

#### Scenario: The command prints the report of the App
- **WHEN** `devops gh metrics` prints a report whose `traffic_collected` is false
- **THEN** its traffic line says "not collected" and shows no count of views or clones

### Requirement: A report without traffic sends no traffic gauge
`emit_project_metrics_telemetry` SHALL send none of the six `devops_cli_project_traffic_*` gauges for a report whose `traffic_collected` is false, and SHALL still send the stars and the forks.

#### Scenario: A round of the metrics row under the App
- **WHEN** the metrics row runs in a process that acts as the GitHub App, and GitHub is faked at the `gh` edge
- **THEN** the row sends no `devops_cli_project_traffic_*` point and sends `devops_cli_project_stars` and `devops_cli_project_forks`

### Requirement: A path that the token cannot read is not asked again
The project metrics collector SHALL NOT send a GitHub path again in the same process after GitHub answered that path with HTTP 403 and the message "Resource not accessible by integration". Another repository, another endpoint and any other failure SHALL NOT set the guard. A new process SHALL start with no refused path.

#### Scenario: Two collections after a refusal
- **WHEN** GitHub answers `repos/example/repo/traffic/views` with 403 "Resource not accessible by integration", and the collector reads the traffic of `example/repo` twice
- **THEN** the path is requested once, and the other three traffic paths are requested twice

#### Scenario: Another repository
- **WHEN** the path of `example/one` was refused and the collector reads the traffic of `example/two`
- **THEN** the path `repos/example/two/traffic/views` is requested

#### Scenario: A failure that is not a refusal by the token
- **WHEN** GitHub answers a traffic path with a 502 or with a 403 of another message, such as "Must have push access", and the collector reads the traffic again
- **THEN** the path is requested again
