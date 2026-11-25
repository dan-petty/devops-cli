## MODIFIED Requirements

### Requirement: The Service image runs the OpenSpec of package-lock.json
The Service image of `Dockerfile` SHALL carry the `node` binary of a digest-pinned `node` image whose major version is the one in `.node-version`, and the OpenSpec that the root `package-lock.json` pins, which the `openspec` stage installs with `npm ci`. The `openspec` stage SHALL keep OpenSpec and only the packages that it needs, and `/usr/local/bin/openspec` SHALL link to it. The stage SHALL set `OPENSPEC_TELEMETRY=0`, `OPENSPEC_NO_UPDATE_CHECK=1` and `DO_NOT_TRACK=1`.

#### Scenario: OpenSpec comes from the root lockfile
- **WHEN** the stage `service-smoke` of `smoke.Dockerfile` runs `openspec --version` on the image
- **THEN** the command prints the `@fission-ai/openspec` version of `package-lock.json` and exits 0

#### Scenario: The telemetry is off
- **WHEN** the environment of the service stage is read
- **THEN** it sets `OPENSPEC_TELEMETRY` to 0, `OPENSPEC_NO_UPDATE_CHECK` to 1 and `DO_NOT_TRACK` to 1

#### Scenario: The Node runtime is the one of CI
- **WHEN** a person runs `docker run --rm --entrypoint node <service image> --version`
- **THEN** the major version equals the content of `.node-version`, because `service-deps` copies the `node` binary from the digest-pinned `node` stage
