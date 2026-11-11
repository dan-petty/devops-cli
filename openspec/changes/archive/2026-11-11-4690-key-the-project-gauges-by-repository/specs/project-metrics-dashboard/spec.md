## ADDED Requirements

### Requirement: Each project series carries the repository of its snapshot
Each point of a `devops_cli_project_*` instrument SHALL carry the label `repo`, the casefolded `owner/name` of the report that holds the value, so the snapshots of two repositories never share a series. The description of each such instrument SHALL name `repo`.

#### Scenario: Two repositories in one process
- **WHEN** a test emits the report of `Example/One` with 2 stars and then the report of `Example/Two` with 7 stars, in one process
- **THEN** each `devops_cli_project_*` instrument has points with `repo=example/one` and points with `repo=example/two`, and the stars points are 2 for `example/one` and 7 for `example/two`

#### Scenario: A reader of the instruments
- **WHEN** a test reads the description of each `devops_cli_project_*` instrument of `INSTRUMENTS`
- **THEN** each description names `repo`, and the description of `devops_cli_project_items` also names `release`, `state`, `type` and `priority`

### Requirement: A snapshot for telemetry holds the whole repository
`devops gh metrics --emit-telemetry` SHALL exit with an error that names the refused option when `--milestone` is given or `--limit` is not its default of 10. It SHALL refuse before any request and send no point. With no `--limit` or with `--limit 10`, it SHALL send the snapshot.

#### Scenario: A filtered snapshot
- **WHEN** a test runs `devops gh metrics --emit-telemetry --milestone 2026-11` and `devops gh metrics --emit-telemetry --limit 5`
- **THEN** each run exits non-zero, its output names the refused option, no `gh` or `git` program runs, and no `devops_cli_project_*` point is sent

#### Scenario: The default limit
- **WHEN** a test runs `devops gh metrics --repo example/repo --emit-telemetry` with no `--limit`, and with `--limit 10`
- **THEN** each run exits 0 and sends the stars point with `repo=example/repo`

## MODIFIED Requirements

### Requirement: A label set that has no items is sent as 0 once
After a snapshot of a repository, `emit_project_metrics_telemetry` SHALL send the value 0, with the `repo` of that repository, for each label set that the last snapshot of the same repository in the same process sent and the new snapshot does not hold. It SHALL send that 0 once, and SHALL send no 0 for a label set of another repository.

#### Scenario: The last item of a label set closes
- **WHEN** a snapshot holds one open item of type `bug`, and the next snapshot of the same repository holds that item as closed
- **THEN** the next snapshot sends 0 for the open set and 1 for the closed set, and the snapshot after it sends neither the 0 nor the open set

#### Scenario: A snapshot of a second repository
- **WHEN** a snapshot of `Example/One` holds one open item of type `bug`, and the next snapshot in the process is of `Example/Two` with one closed item of type `feature`
- **THEN** the snapshot of `Example/Two` sends only its closed set with `repo=example/two`, and no point with the value 0

#### Scenario: A label set leaves one of two repositories
- **WHEN** snapshots of `Example/One` and `Example/Two` each hold one open item of type `bug`, and the next snapshot of `Example/One` holds that item as closed
- **THEN** that snapshot sends 0 for the open set and 1 for the closed set, both with `repo=example/one`, and sends no point with `repo=example/two`
