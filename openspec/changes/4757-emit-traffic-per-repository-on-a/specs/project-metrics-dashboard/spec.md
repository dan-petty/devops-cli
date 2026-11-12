## MODIFIED Requirements

### Requirement: The Service collects no repository traffic
A process that acts as the GitHub App SHALL send one request to each of the four repository traffic endpoints (`traffic/views`, `traffic/clones`, `traffic/popular/referrers` and `traffic/popular/paths`) when it collects the project metrics, and the report SHALL have `traffic_collected` true. A token without `administration: read` SHALL leave `traffic_collected` false.

#### Scenario: A run from a workstation
- **WHEN** `get_repository_traffic_metrics` runs in a process that does not act as the App
- **THEN** it sends one request to each of the four traffic paths and the report has `traffic_collected` true

#### Scenario: A collection under the App
- **WHEN** `get_repository_traffic_metrics` runs in a process that acts as the GitHub App whose installation token holds `administration: read`, and GitHub is faked at the `gh` edge
- **THEN** it sends one request to each of the four traffic paths and the report has `traffic_collected` true

#### Scenario: The command prints the report of the App
- **WHEN** `devops gh metrics` prints a report whose `traffic_collected` is false
- **THEN** its traffic line says "not collected" and shows no count of views or clones

### Requirement: A path that the token cannot read is not asked again
The project metrics collector SHALL NOT send a GitHub path again in the same process after GitHub answered that path with HTTP 403 and the message "Resource not accessible by integration". A traffic refusal SHALL add the repository to the refused set and SHALL log one warning that names it and `administration: read`. Another repository, another endpoint and any other failure SHALL NOT set the guard. A new process SHALL start with no refused path.

#### Scenario: Two collections after a refusal
- **WHEN** GitHub answers `repos/example/repo/traffic/views` with 403 "Resource not accessible by integration", and the collector reads the traffic of `example/repo` twice
- **THEN** the views path is requested once, the other three traffic paths are requested once, one warning names `administration: read`, and the second collection sends no traffic request for `example/repo`

#### Scenario: Another repository
- **WHEN** the path of `example/one` was refused and the collector reads the traffic of `example/two`
- **THEN** the path `repos/example/two/traffic/views` is requested

#### Scenario: A failure that is not a refusal by the token
- **WHEN** GitHub answers a traffic path with a 502 or with a 403 of another message, such as "Must have push access", and the collector reads the traffic again
- **THEN** the path is requested again
