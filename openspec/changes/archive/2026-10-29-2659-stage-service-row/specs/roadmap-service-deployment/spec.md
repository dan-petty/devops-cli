## ADDED Requirements

### Requirement: The Service image runs the pinned OpenSpec
The service stage of `Dockerfile` SHALL carry the `node` binary of a digest-pinned `node` image whose major version is the one in `.node-version`, and the OpenSpec that `devops install-tools --tool openspec` installs from the lockfile of `src/devops_cli/tools_lock/openspec`. The directory of its `openspec` link SHALL be on the `PATH` of the stage. The stage SHALL set `OPENSPEC_TELEMETRY=0`, `OPENSPEC_NO_UPDATE_CHECK=1` and `DO_NOT_TRACK=1`.

#### Scenario: OpenSpec comes from the lockfile
- **WHEN** the builder stage and the service stage of `Dockerfile` are read
- **THEN** the builder stage runs `devops install-tools --tool openspec` with a `--target-dir`, the service stage copies the tool directory from the builder to the same path, and that `--target-dir` is on the `PATH` of the service stage

#### Scenario: The telemetry is off
- **WHEN** the environment of the service stage is read
- **THEN** it sets `OPENSPEC_TELEMETRY` to 0, `OPENSPEC_NO_UPDATE_CHECK` to 1 and `DO_NOT_TRACK` to 1

#### Scenario: The Node runtime is the one of CI
- **WHEN** the `node` stage of `Dockerfile` is read
- **THEN** its image is pinned by digest and its major version equals the content of `.node-version`, and the builder stage and the service stage copy the `node` binary from it
