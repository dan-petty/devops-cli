# Proposal

## Why

Issue #5573: three entries of `.trivyignore-mcp-server` expired on 2026-11-14. Since then, the check `MCP Server Image` and the invariant test `test_every_mcp_server_trivyignore_entry_has_a_reason_and_an_exp_date_that_is_not_past` fail on each pull request. The test runs in the required check `Tests & Coverage`, so no pull request can merge. The helm release v4.3.2 holds the fix of one finding. No kubectl release holds the fix of the two other findings.

## What Changes

- Bump the pin of helm from 4.3.1 to 4.3.2 in `src/devops_cli/tools_lock/tools.lock` and in `.devcontainer/Dockerfile`. Each `sha256` is the digest in the `<archive>.sha256sum` file of get.helm.sh.
- Delete the entry of CVE-2026-111943 from `.trivyignore-mcp-server`. Helm 4.3.2 has Go 1.27.4, which holds the fix.
- Renew the entries of CVE-2026-56851 and CVE-2026-78669 for 3 days, to 2026-11-17. The first entries are from 2026-11-08, so the limit of 14 days in all is 2026-11-22. Issue #5582 tracks the bump of kubectl that removes both entries.
- Raise the floor of helm in `tests/invariants/test_mcp_server_image.py` to 4.3.2, and make the test fail when the ignore file lists CVE-2026-111943.
- The change has no spec delta and sets `skip_specs: true`: it changes a tool pin, a test and the configuration of a scanner. The requirement "Pinned cluster tools" of `mcp-server-image` stays true.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/tools_lock/tools.lock` (helm), and so the images `runner`, `mcp-server` and `service`, which install helm from it.
- `.devcontainer/Dockerfile` (helm), which a test keeps equal to `tools.lock`.
- `.trivyignore-mcp-server`, which the scan of the `mcp-server` image reads in CI and in the release.
- No path under `k8s/` changes, so no manifest changes.

## Feasibility

Read on 2026-11-14 against `origin/main` at `ffce5d999`.

- `uv run pytest tests/invariants/test_mcp_server_image.py` on the base: the test of the expiry dates fails with `CVE-2026-111943 ... expired on 2026-11-14` and two more lines of the same kind.
- The log of the failed job `MCP Server Image` of run 43530882341 (2026-11-14 00:00 UTC, Trivy v0.76.2) has three findings and no other: CVE-2026-111943 in `opt/devops-tools/tools/helm/4.3.1/helm` (stdlib v1.27.2), and CVE-2026-78669 and CVE-2026-56851 in `opt/devops-tools/tools/kubectl/1.37.2/kubectl`.
- `devops gh api repos/helm/helm/releases`: v4.3.2 is the newest release (2026-11-13), and it is not a pre-release. The four `.sha256sum` files of get.helm.sh agree with `sha256sum` of the four archives.
- Trivy 0.75.0 (`trivy rootfs --scanners vuln --list-all-pkgs`) on the helm 4.3.2 linux-amd64 binary: stdlib v1.27.4, golang.org/x/net v0.62.0, golang.org/x/text v0.43.0, and no HIGH or CRITICAL finding. The same scan on helm 4.3.1 shows CVE-2026-111943 (stdlib v1.27.2, fix 1.27.3).
- `devops gh api repos/kubernetes/kubernetes/releases` and `https://dl.k8s.io/release/stable.txt`: v1.37.2 is the newest stable release, and v1.38.0-beta.0 is a pre-release. Trivy on the kubectl 1.37.2 binary shows x/net v0.57.0 (CVE-2026-78669) and x/text v0.40.0 (CVE-2026-56851). Thus no released kubectl holds the fix, and SECURITY.md "A Finding with No Fix" lets an agent renew the two entries.
- `trivy rootfs --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1` on the helm 4.3.2 and kubectl 1.37.2 binaries, with `.trivyignore` and the new `.trivyignore-mcp-server`: exit 0, no finding.
- A local build of the `mcp-server` image stopped: the registry of this environment refused the pull of `ghcr.io/astral-sh/uv`. The CI check `MCP Server Image` is the scan of the full image.

## Existing Tool Considered

Trivy and its `.trivyignore` format are the open tools, and `tools.lock` is the pin of each tool. The change builds no code and deletes no code.
