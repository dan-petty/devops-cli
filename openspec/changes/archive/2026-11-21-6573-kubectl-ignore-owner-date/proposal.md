# Proposal: #6573

## Why

Issue #6573: the entries of CVE-2026-78661 and CVE-2026-78669 in `.trivyignore.yaml` (golang.org/x/net v0.57.0 in `usr/local/bin/kubectl`) expired on 2026-11-21. Since then, the check `MCP Server Image` fails on each pull request that builds the image. The entries of CVE-2026-56851 and CVE-2026-97054 expire on 2026-11-22. No stable kubectl release holds the fixes. The 14-day limit of SECURITY.md "A Finding with No Fix" ends on 2026-11-22 for the oldest entries, so an agent cannot renew them. On 2026-11-21, the owner extended the four entries to 2026-12-15.

## What Changes

- Set `expired_at: 2026-12-15` on the four kubectl entries of `.trivyignore.yaml`: CVE-2026-56851, CVE-2026-78669, CVE-2026-78661 and CVE-2026-97054. The ids, `paths` and `purls` do not change.
- Each `statement` names the newest stable release on 2026-11-21, the fixed version, the owner decision and the tracking issue #6084.
- The change has no spec delta and sets `skip_specs: true`: it changes only the configuration of a scanner.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `.trivyignore.yaml`, which the image scan action reads for the Service, runner and MCP server images. The entries name only `usr/local/bin/kubectl`, which only the MCP server image holds.
- No tool pin, no image content and no path under `k8s/` changes. The kubectl bump of #6084 deletes the entries.

## Feasibility

Read on 2026-11-21 against `origin/main` at `b06cbef62`.

- The failed job `MCP Server Image` 136648122309 (Trivy v0.76.2) names CVE-2026-78661 (x/net v0.57.0, fixed in 0.62.0) and CVE-2026-78669 (x/net v0.57.0, fixed in 0.60.0) in `usr/local/bin/kubectl`.
- `Dockerfile` copies kubectl from the devtools image, and the devtools repository pins `kubectl = "1.37.2"` in `mise.toml`.
- `https://dl.k8s.io/release/stable.txt` and `stable-1.37.txt` give v1.37.2 (2026-10-28). No tag v1.37.3 exists. v1.38.0-beta.0 (2026-11-06) is a pre-release.
- `go.mod` of kubernetes/kubernetes: v1.37.2 and `release-1.37` hold x/net v0.57.0 and x/text v0.40.0. v1.38.0-beta.0 holds x/net v0.62.0 and x/text v0.43.0.
- `git log -S` gives the first kubectl entries: CVE-2026-78669 and CVE-2026-56851 on 2026-11-08 (#4182), CVE-2026-78661 on 2026-11-14 (#5785), and CVE-2026-97054 on 2026-11-18 (#6370). A path-less gh entry of CVE-2026-78661 in `.trivyignore` also hid that id in the MCP server scan from 2026-11-08.
- Trivy v0.76.2 (DB of 2026-11-20) with `trivy rootfs --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1` on a root with the kubectl v1.37.2 binary at `usr/local/bin/kubectl`: exit 1 with the ignore file of `main` (CVE-2026-78661 and CVE-2026-78669), exit 0 with the file of this change.

## Existing Tool Considered

Trivy and its `.trivyignore.yaml` format are the open tools. The change builds no code and deletes no code.
