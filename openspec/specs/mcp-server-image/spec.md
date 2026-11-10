# mcp-server-image Specification

## Purpose
The container image target for the MCP server that serves role-scoped tool sets to cluster jobs.

## Requirements

### Requirement: MCP server image target
The `Dockerfile` SHALL add an `mcp-server` target that inherits the `runner` stage.

#### Scenario: Target inherits runner
- **WHEN** A test parses the stages of the `Dockerfile`.
- **THEN** The stage `mcp-server` exists and its `FROM` line names `runner`.

### Requirement: Pinned cluster tools
The `mcp-server` target SHALL install `kubectl` and `helm` at the versions that `tools.lock` pins.

#### Scenario: Tool pins match
- **WHEN** The image build runs the tool version check.
- **THEN** Each installed version equals its pin, and a mismatch fails the build and names the tool.

### Requirement: Runtime user and directories
The `mcp-server` target SHALL run as user `1000:1000` and SHALL keep the data and uv cache directories under `HOME`.

#### Scenario: Runtime user is non-root
- **WHEN** A test reads the `USER` and `ENV` lines of the `mcp-server` stage.
- **THEN** `USER` is `1000:1000` and `DEVOPS_CLI_DATA_DIR` and `UV_CACHE_DIR` start with `HOME`.

### Requirement: MCP server image gate
The `mcp-server` image SHALL pass the HIGH and CRITICAL vulnerability scan and SHALL stay at or below 3,000,000,000 bytes.

#### Scenario: Image gate passes
- **WHEN** CI builds the `mcp-server` image.
- **THEN** `trivy image` exits 0 and `docker image inspect` reports at most 3,000,000,000 bytes.

### Requirement: Default Docker build stays on service
The `service` stage SHALL stay the last stage of the `Dockerfile`.

#### Scenario: Service stage is last
- **WHEN** A test lists the stages of the `Dockerfile`.
- **THEN** The last stage is `service` and `mcp-server` comes before it.

### Requirement: The release publishes the MCP server image
The `release.yml` workflow SHALL build, smoke-test, scan, push by digest, attest and tag the `mcp-server` image, in that order, only in the run that creates a release. It SHALL tag the image with the release tag and `latest`.

#### Scenario: Publish job order
- **WHEN** A test reads job `mcp-server-image` of `release.yml`.
- **THEN** The job needs `release-please`, runs only when `release_created` is `true`, builds target `mcp-server`, pushes with `push-by-digest=true`, attests `ghcr.io/${{ github.repository }}/mcp-server`, and its steps keep the order of the `runner-image` job.

### Requirement: The release gate equals the pull request gate
The smoke test and the vulnerability scan of the release job SHALL equal those of job `mcp-server-image` in `ci.yml`.

#### Scenario: Same smoke test and scan
- **WHEN** A test compares the two jobs.
- **THEN** The smoke test scripts are equal and the inputs of the Trivy steps are equal.

### Requirement: Each image of this repository in k8s has a publish job
Each value of the keys `image` and `imageName` under `k8s/` that starts with `ghcr.io/dan-petty/devops-cli/` SHALL name an image that a job of `release.yml` attests.

#### Scenario: Manifest names an unpublished image
- **WHEN** A manifest under `k8s/` names `ghcr.io/dan-petty/devops-cli/<name>` and no job of `release.yml` attests `<name>`.
- **THEN** The test fails and names the image and the file.
