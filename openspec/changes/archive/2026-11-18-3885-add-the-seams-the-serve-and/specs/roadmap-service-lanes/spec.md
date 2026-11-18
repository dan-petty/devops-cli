## ADDED Requirements

### Requirement: The app state holds each lane's table and clone directory
`create_service_app` SHALL set `app.state.lanes` to one `LaneSpec` for each lane that `service_jobs` builds, with the name, the table and the clone directory of the lane.

#### Scenario: Service wiring reads the lane tables
- **WHEN** A test runs `devops serve --service` with the fake starter and reads the app that the fake built.
- **THEN** `app.state.lanes` holds one `LaneSpec` for each key of `app.state.jobs`, and each spec holds the rows of its lane and the clone directory `lanes/<lane>`.
