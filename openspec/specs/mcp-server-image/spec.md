# mcp-server-image Specification

## Purpose
The container image target for the MCP server that serves role-scoped tool sets to cluster jobs.

## Requirements

### Requirement: Runtime user and directories
The `mcp-server` target SHALL run as user `1000:1000` and SHALL keep the data directory under `HOME`.

#### Scenario: Runtime user is non-root
- **WHEN** the smoke test runs `docker run --rm --entrypoint id "$IMAGE" -u`
- **THEN** the command prints `1000`

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
The release SHALL build the `mcp-server` target one time and push it by digest, then smoke-test, scan, attest and tag that digest, in that order, only in the run that creates a release. It SHALL tag the image with the release tag and `latest`. The build SHALL set `no-cache-filters: mcp-server`.

#### Scenario: Publish job order
- **WHEN** a person reads the `MCP Server Image` jobs of the first release after the merge with `uv run devops gh run view <run_id>`
- **THEN** `Build` ran first, then `Verify`, then `Attest & Tag`, and `docker buildx imagetools inspect ghcr.io/dan-petty/devops-cli/mcp-server:latest` gives the digest that `Build` pushed

### Requirement: The release gate equals the pull request gate
The smoke test of the release job SHALL equal that of job `mcp-server-image` in `ci.yml`, and both jobs SHALL scan the image with `.github/actions/image-scan` under the category `trivy-image-mcp-server`.

#### Scenario: Same smoke test and scan
- **WHEN** A developer compares the two jobs and runs `git grep -c 'category: trivy-image-mcp-server' .github/workflows/ci.yml .github/workflows/release.yml`.
- **THEN** The smoke test scripts are equal, and the command prints a count of 1 for each file.

### Requirement: Each image of this repository in k8s has a publish job
Each value of the keys `image` and `imageName` under `k8s/` that starts with `ghcr.io/dan-petty/devops-cli/` SHALL name an image that a job of `release.yml` attests.

#### Scenario: Manifest names an unpublished image
- **WHEN** A manifest under `k8s/` names `ghcr.io/dan-petty/devops-cli/<name>` and no job of `release.yml` attests `<name>`.
- **THEN** The test fails and names the image and the file.

### Requirement: The MCP server image builds on the Service image layers
The `Dockerfile` SHALL add an `mcp-server` target that builds on `mcp-server-deps`, which builds on `service-deps` and so on `python:3.14-slim-trixie`, as the Service image does. It SHALL NOT build on the `runner` stage, and it SHALL hold no uv and no dev dependency.

#### Scenario: The target holds no build tool
- **WHEN** a person builds `--target mcp-server` and runs `docker run --rm --entrypoint sh <image> -c 'command -v uv'`
- **THEN** the build exits 0 and the command exits non-zero

### Requirement: The MCP server image copies its cluster tools from the devtools image
The `mcp-server` target SHALL copy `kubectl` and `helm` from the devtools image that the `Dockerfile` pins by digest, and SHALL hold gh, git and OpenSpec as the Service image does. The `Dockerfile` SHALL name no version of these tools.

#### Scenario: The cluster tools run
- **WHEN** the smoke test of the MCP Server Image job runs `docker run --rm --entrypoint kubectl "$IMAGE" version --client` and `docker run --rm --entrypoint helm "$IMAGE" version`
- **THEN** each command exits 0 and prints the version of the devtools image
