# Proposal

## Why

Issue #4336: the five entries of `.trivyignore-mcp-server` expire on 2026-11-11. From that day the check `mcp-server-image`, the test of the entries and the release job for the mcp-server image fail. Newer releases of the two pinned tools hold some of the fixes, so a plain renewal is wrong for those findings.

## What Changes

- Bump the pin of kubectl from 1.37.1 to 1.37.2 and the pin of helm from 4.3.0 to 4.3.1 in `tools.lock`. Each `sha256` is the digest in the file of the publisher (`kubectl.sha256` of dl.k8s.io, `<archive>.sha256sum` of get.helm.sh).
- Delete the entries of CVE-2026-78667 and CVE-2026-97031 from `.trivyignore-mcp-server`. The new releases remove both findings.
- Renew the entries of CVE-2026-111943, CVE-2026-56851 and CVE-2026-78669 for 3 days, to 2026-11-14. No release of kubectl or helm holds the fix. The first entries are from 2026-11-08, so the limit of 14 days in all is 2026-11-22.
- The change has no spec delta and sets `skip_specs: true`: it changes a tool pin and scanner configuration.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/tools_lock/tools.lock` (kubectl and helm), and so the images `runner`, `mcp-server` and `service`, which install both tools from it.
- `.trivyignore-mcp-server`.

## Feasibility

Read on 2026-11-10. Both releases are older than 2 weeks (kubectl 1.37.2 on 2026-10-28, helm 4.3.1 on 2026-10-15).

- Trivy 0.75.0 (`trivy rootfs --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed`) on the release binaries, with the digests checked:
  - kubectl 1.37.1: x/net 0.57.0 (CVE-2026-78661, CVE-2026-78669), x/text 0.40.0 (CVE-2026-56851), stdlib 1.26.8 (CVE-2026-111943, CVE-2026-78667, CVE-2026-78669, CVE-2026-97031).
  - kubectl 1.37.2 (`.go-version` is 1.26.10): CVE-2026-78661, CVE-2026-78669 and CVE-2026-56851 remain. All stdlib findings are gone.
  - helm 4.3.0: x/net 0.57.0 and stdlib 1.27.1, five findings.
  - helm 4.3.1 (x/net 0.60.0, x/text 0.43.0): CVE-2026-78661 and CVE-2026-111943 (stdlib 1.27.2, fix 1.27.3) remain.
- CVE-2026-78661 stays under the entry of `.trivyignore` (owner decision, expires 2026-11-21, tracked in #3920).
- No kubectl or helm release holds the fix of the three renewed findings: kubectl 1.37.2 is the newest stable release of kubernetes/kubernetes and helm 4.3.1 the newest of helm/helm.

## Existing Tool Considered

Trivy and its `.trivyignore` format are the open tools. The change builds no code. It adds one invariant test for the floor of the two pins, and the test of the version skew reads the kubectl version from the lock.
