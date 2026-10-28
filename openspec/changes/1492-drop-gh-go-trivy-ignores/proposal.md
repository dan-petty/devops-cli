# Proposal

## Why

Issue #1492: the Service image installed gh v2.102.0, which cli/cli builds with Go 1.27.1 and `golang.org/x/net` v0.58.0. Trivy failed the image on HIGH denial-of-service findings in that build. `.trivyignore` ignored three of them until 2026-10-23: CVE-2026-78667, CVE-2026-97031 and CVE-2026-78669.

The fix of #1800 moved the Dockerfile to gh v2.102.1, which cli/cli builds with Go 1.27.3 and `golang.org/x/net` v0.60.0. That build does not have the three findings. The three ignores stayed in `.trivyignore`, and their reason still names gh v2.102.0 and Go 1.27.1. No check stops an ignore from staying after the pin that needs it moves.

## What Changes

- Delete the three ignores and their reason from `.trivyignore`. The file keeps its header.
- Keep the gh pin at v2.102.1. It already is a release built with Go 1.27.2 or later, with the SHA-256 of each tarball.
- Add two invariant tests in `tests/test_service_image_gh.py`. One fails when the Dockerfile fetches gh from more than one release, or from a release below v2.102.1. The other fails when `.trivyignore` ignores one of the three findings again.
- The change has no spec delta and sets `skip_specs: true`. The three ignores expired on 2026-10-23, so Trivy already applies none of them. The image, its scan result and every `devops` command stay the same.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Scanner configuration: `.trivyignore`. The CI job `Service Image` watches this file, so the pull request builds and scans the Service image.
- Tests: `tests/test_service_image_gh.py`.

## Feasibility

- `Dockerfile` on `origin/main` (bb46660c) fetches `gh_2.102.1_linux_amd64.tar.gz` and `gh_2.102.1_linux_arm64.tar.gz` from the release `v2.102.1`. `.trivyignore` lists the three findings with `exp:2026-10-23`.
- The `go.mod` of cli/cli at the tag `v2.102.1` has `toolchain go1.27.3` and `golang.org/x/net v0.60.0` (`devops gh api repos/cli/cli/contents/go.mod?ref=v2.102.1`). The release notes of v2.102.1 say that the release only moves Go from 1.27.1 to 1.27.3 and `golang.org/x/net` from 0.58.0 to 0.60.0.
- The `linux_amd64` binary of v2.102.1 holds the build information `go1.27.3` and `golang.org/x/net v0.60.0`. Its tarball matches the `--checksum` of the Dockerfile.
- Trivy 0.75.0, with the vulnerability database of 2026-10-28, scans the gh binaries with `--severity HIGH,CRITICAL --ignore-unfixed` and no ignore file. The v2.102.0 binary gives CVE-2026-78667, CVE-2026-97031 and CVE-2026-78669 (Go 1.27.1, `golang.org/x/net` v0.58.0), and CVE-2026-111943. The v2.102.1 binary gives no finding.
- The release run 40626081164 of v0.8.2, on 2026-10-28, passed the step "Scan Service Image for Vulnerabilities". The ignores had expired at that time, so the image needs none of them.
- The newest gh release is v2.103.3. Its `go.mod` has the same toolchain and the same `golang.org/x/net`, and its Trivy scan also gives no finding. No cli/cli security advisory names v2.102.1 as vulnerable.

## Existing Tool Considered

Trivy is the open tool that finds the vulnerabilities, and `.trivyignore` is its own ignore format. The change uses both as they are. Trivy does not report an ignore that matches no finding, so the second test holds this item. The change builds no code. It deletes the three ignores and their reason.
