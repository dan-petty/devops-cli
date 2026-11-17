# cloudflared-release-pin Specification

## Purpose
The cloudflared release that the tunnel Deployment runs and that `devops install-tools` installs. Every pin holds a release that rejects the eight eMudhra intermediate certificates with weak private keys, so a forged certificate does not pass for a Cloudflare host or an origin.

## Requirements

### Requirement: The tunnel Deployment runs a cloudflared release that rejects the compromised eMudhra intermediates
The container image of Deployment `cloudflared` in `k8s/cloudflared/deployment.yaml` SHALL be the repository `cloudflare/cloudflared` at tag 2026.10.2 or later. The container runs with `--no-autoupdate`, so only a change of this tag changes the release.

#### Scenario: The Deployment names an image below the first safe release
- **WHEN** a person runs `kubectl -n cloudflared get pods -o jsonpath='{range .items[*]}{.status.containerStatuses[*].image} {.status.containerStatuses[*].imageID}{"\n"}{end}'`
- **THEN** each tunnel pod runs the image `cloudflare/cloudflared` with a tag of 2026.10.2 or later, the tag of Deployment `cloudflared`
- **AND** each `imageID` holds the same digest
- **AND** `uv run devops k8s image-pins k8s/cloudflared` resolves the image of the repository `cloudflare/cloudflared` in its registry

### Requirement: The tools lock installs a cloudflared release that rejects the compromised eMudhra intermediates
The `cloudflared` entry of `tools.lock` SHALL have a `version` of 2026.10.2 or later. The `url` of each platform build SHALL name the GitHub release of that `version`, so the checksum of a build and the version it installs under always belong to one release.

#### Scenario: The lock pins a version below the first safe release
- **WHEN** a person runs `uv run devops install-tools --tool cloudflared --target-dir <dir>`
- **THEN** the install checks the sha256 of the build of the host
- **AND** `<dir>/cloudflared --version` prints a version of 2026.10.2 or later

#### Scenario: A platform build comes from another release than the locked version
- **WHEN** a person runs `uv run devops install-tools --tool cloudflared --dry-run` on a `linux-amd64`, `linux-arm64`, `darwin-amd64` or `darwin-arm64` host
- **THEN** the one request is a `GET` of a URL that starts with `https://github.com/cloudflare/cloudflared/releases/download/<version>/`
- **AND** `<version>` is the `Pinned` version that `uv run devops install-tools status` shows for `cloudflared`
