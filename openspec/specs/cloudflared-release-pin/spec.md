# cloudflared-release-pin Specification

## Purpose
The cloudflared release that the tunnel Deployment runs and that `devops install-tools` installs. Every pin holds a release that rejects the eight eMudhra intermediate certificates with weak private keys, so a forged certificate does not pass for a Cloudflare host or an origin.

## Requirements

### Requirement: The tunnel Deployment runs a cloudflared release that rejects the compromised eMudhra intermediates
The container image of Deployment `cloudflared` in `k8s/cloudflared/deployment.yaml` SHALL be the repository `cloudflare/cloudflared` at tag 2026.10.2 or later. The container runs with `--no-autoupdate`, so only a change of this tag changes the release.

#### Scenario: The Deployment names an image below the first safe release
- **WHEN** a test reads the image of the container of Deployment `cloudflared` in `k8s/cloudflared/deployment.yaml`
- **THEN** the image repository is `cloudflare/cloudflared`
- **AND** the image tag, read as a version, is 2026.10.2 or later

### Requirement: The tools lock installs a cloudflared release that rejects the compromised eMudhra intermediates
The `cloudflared` entry of `tools.lock` SHALL have a `version` of 2026.10.2 or later. The `url` of each platform build SHALL name the GitHub release of that `version`, so the checksum of a build and the version it installs under always belong to one release.

#### Scenario: The lock pins a version below the first safe release
- **WHEN** a test loads the tools lock that devops-cli ships
- **THEN** the `version` of the `cloudflared` binary tool, read as a version, is 2026.10.2 or later

#### Scenario: A platform build comes from another release than the locked version
- **WHEN** a test reads the `url` of every platform build of the `cloudflared` binary tool
- **THEN** the platforms are `linux-amd64`, `linux-arm64`, `darwin-amd64` and `darwin-arm64`
- **AND** every `url` starts with `https://github.com/cloudflare/cloudflared/releases/download/<version>/`, where `<version>` is the locked `version`
