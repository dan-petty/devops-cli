## ADDED Requirements

### Requirement: The image checks that need no container are build stages
`smoke.Dockerfile` SHALL define the stages `service-smoke`, `mcp-server-smoke`, `runner-smoke` and `uv-seed-smoke`, each of which starts from the image that a build argument names, by default the local tag of the target. The image jobs of `ci.yml` and the `Verify` job of `release-image.yml` SHALL build the stage of each image that they check, and a failed check SHALL fail the build. A release MUST NOT publish a stage of this file.

#### Scenario: The stage runs on the image under test
- **WHEN** a developer builds the `service` target and tags it `devops-cli-service:local` and runs `docker build -f smoke.Dockerfile --target service-smoke .`
- **THEN** the build exits 0

#### Scenario: A forbidden tool fails the stage
- **WHEN** the image that `SERVICE_IMAGE` names holds `uv`
- **THEN** the build of `service-smoke` exits non-zero

#### Scenario: The release tests the pushed digest
- **WHEN** the `Verify` job of an image runs
- **THEN** it builds the stage of that image with the pushed digest as its build argument
