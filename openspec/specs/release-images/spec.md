# release-images Specification

## Purpose
How the release publishes the service, runner and mcp-server images: it builds each image one time, pushes it by digest, smoke-tests and scans that digest, and only then attests it and puts the release tags on it, one image at a time.

## Requirements

### Requirement: One build per image
The release SHALL build each of the service, runner and mcp-server images in one job of `.github/workflows/release-image.yml` and push that build by digest, with no tag, an SBOM and provenance `mode=max`. It MUST NOT build an image a second time to load, smoke-test or scan it. The revision label of the image SHALL be the commit that the release tags.

#### Scenario: The release run builds each image once
- **WHEN** a person reads the logs of the first release after the merge with `uv run devops gh run view <run_id> --log`
- **THEN** the `Build` job of each image shows one `exporting manifest list` digest, and the `Verify` and `Attest & Tag` jobs of that image name the same digest

### Requirement: Each image promotes on its own
`.github/workflows/release.yml` SHALL call `release-image.yml` from one job whose matrix names `service`, `runner` and `mcp-server`, with `fail-fast: false`. A failed job of one image MUST NOT cancel or skip a job of another image.

#### Scenario: The workflows are validated
- **WHEN** a developer runs `uv run devops ci --check --only actionlint,zizmor`
- **THEN** the command exits 0, and actionlint checks each input of the call against the inputs of `release-image.yml`

#### Scenario: One image fails Verify
- **WHEN** the `Verify` job of one image fails in a release run
- **THEN** `uv run devops gh run view <run_id>` shows the `Build`, `Verify` and `Attest & Tag` jobs of the other images as passed, and the failed image has no new tag

### Requirement: Verify can write no package
The `Verify` job SHALL pull the pushed digest, run the smoke test of the image that `ci.yml` runs, and scan the digest with `.github/actions/image-scan`. It SHALL hold only `contents: read`, `packages: read` and `security-events: write`, and MUST NOT get an OIDC token.

#### Scenario: zizmor reports no excess permission
- **WHEN** a developer runs `uv run devops ci --check --only zizmor`
- **THEN** the command exits 0 and reports no finding in `.github/workflows/release-image.yml`

### Requirement: Attest then tag the verified digest
The `Attest & Tag` job SHALL run only after `Verify` passed. It SHALL attest the pushed digest with `actions/attest`, then put the release tag and `latest` on that digest with `docker buildx imagetools create`, and MUST fail when `docker buildx imagetools inspect` of a tag gives another digest.

#### Scenario: The tags name the scanned digest
- **WHEN** a person runs `docker buildx imagetools inspect ghcr.io/dan-petty/devops-cli/<image>:<release tag>` and the same command for `latest` after the first release after the merge
- **THEN** each command gives the digest that the `Build` job of that image pushed and that its `Verify` job scanned
