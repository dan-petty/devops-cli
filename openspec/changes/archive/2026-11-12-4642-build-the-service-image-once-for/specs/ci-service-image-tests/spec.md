## ADDED Requirements

### Requirement: The shards load one build of the Service image
The Service Image Tests workflow SHALL build the `service` stage once per run in a job that the shards need, and SHALL pass it to them as an artifact. Each shard SHALL load that image, SHALL have no build step, and SHALL print its 10 slowest tests and the reason for each skip.

#### Scenario: A run of the workflow
- **WHEN** the workflow runs
- **THEN** one job builds the `service` stage, and each of the six shards loads the image of that job

#### Scenario: A shard builds the image again
- **WHEN** a shard job has a `docker/build-push-action` step
- **THEN** the architectural invariant test fails
