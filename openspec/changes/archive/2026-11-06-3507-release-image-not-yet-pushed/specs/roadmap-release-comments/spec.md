## ADDED Requirements

### Requirement: A missing tag of a new release is not yet
The row `release_comments` SHALL treat an HTTP 404 for the `service` or the `runner` tag of a release that is less than 20 minutes old as not yet built, with no failure. The row SHALL skip that release in the round, SHALL continue with the older releases of the window, and SHALL read the release again in a later round. A skipped release SHALL get no `Live since` comment and SHALL stay not done in the ledger.

#### Scenario: A 404 on a release younger than the limit
- **WHEN** a round reads the `service` tag of a release that is 5 minutes old and the registry answers HTTP 404
- **THEN** the round raises nothing and the release gets no `Live since` comment

#### Scenario: A 404 on the runner tag
- **WHEN** a round reads the `runner` tag of a release that is 5 minutes old, the registry answers HTTP 404, and the `service` tag has a digest
- **THEN** the round raises nothing and the release waits for a later round

#### Scenario: New release missing, older release live
- **WHEN** the registry answers HTTP 404 for the newest release, which is 5 minutes old, and holds both digests of an older release that the cluster runs
- **THEN** the older release gets its `Live since` comment in the same round

#### Scenario: The images are pushed in a later round
- **WHEN** a later round finds both digests of the release and the cluster runs them
- **THEN** the release gets its `Live since` comment

#### Scenario: Three rounds with the same 404
- **WHEN** the status lane runs the row 3 times while the newest release is less than 20 minutes old and its tag gives HTTP 404
- **THEN** each round ends without a failure and the row is not suspended

### Requirement: A missing tag of an older release and other read errors fail
The row SHALL fail with `RoadmapRunError` for an HTTP 404 on a tag of a release that is 20 minutes old or older. The row SHALL fail for each other registry status, also on a release younger than 20 minutes.

#### Scenario: A 404 on a release at the limit
- **WHEN** a round reads the `service` tag of a release that is 20 minutes old and the registry answers HTTP 404
- **THEN** the row raises `RoadmapRunError` that names the release

#### Scenario: HTTP 500 on a new release
- **WHEN** a round reads the `service` tag of a release that is 5 minutes old and the registry answers HTTP 500
- **THEN** the row raises `RoadmapRunError` that names the release
