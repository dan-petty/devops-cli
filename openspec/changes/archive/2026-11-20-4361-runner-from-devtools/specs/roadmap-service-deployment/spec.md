## MODIFIED Requirements

### Requirement: The Service image runs the pinned OpenSpec
The Service image of `Dockerfile` SHALL carry the `node` binary of a digest-pinned `node` image whose major version is the one in `.node-version`, and the OpenSpec of the devtools image that the `Dockerfile` pins by digest. The `openspec` stage SHALL keep OpenSpec and only the packages that it needs, and `/usr/local/bin/openspec` SHALL link to it. The stage SHALL set `OPENSPEC_TELEMETRY=0`, `OPENSPEC_NO_UPDATE_CHECK=1` and `DO_NOT_TRACK=1`.

#### Scenario: OpenSpec comes from the devtools image
- **WHEN** the smoke test of the Service Image job runs `docker run --rm --entrypoint openspec "$IMAGE" --version`
- **THEN** the command prints the OpenSpec version of the devtools image and exits 0

#### Scenario: The telemetry is off
- **WHEN** the environment of the service stage is read
- **THEN** it sets `OPENSPEC_TELEMETRY` to 0, `OPENSPEC_NO_UPDATE_CHECK` to 1 and `DO_NOT_TRACK` to 1

#### Scenario: The Node runtime is the one of CI
- **WHEN** a person runs `docker run --rm --entrypoint node <service image> --version`
- **THEN** the major version equals the content of `.node-version`, because `service-deps` copies the `node` binary from the digest-pinned `node` stage
