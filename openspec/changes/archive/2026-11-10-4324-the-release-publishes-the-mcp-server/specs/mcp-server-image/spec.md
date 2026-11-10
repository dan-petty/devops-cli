## Purpose
The container image target for the MCP server that serves role-scoped tool sets to cluster jobs.

## ADDED Requirements

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
