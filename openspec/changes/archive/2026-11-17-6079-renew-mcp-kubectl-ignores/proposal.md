# Proposal: #6079

## Why

Issue #6079: the three entries of `.trivyignore-mcp-server` for the pinned kubectl v1.37.2 expired on 2026-11-17. Since 00:00 UTC, the check `MCP Server Image` fails on CVE-2026-56851, and the invariant test `test_every_mcp_server_trivyignore_entry_has_a_reason_and_an_exp_date_that_is_not_past` fails in `Changed-Test Independence` and in `Tests & Coverage`. These checks fail on `main` and on each pull request. No released kubectl holds the fixes.

## What Changes

- Renew the entries of CVE-2026-56851, CVE-2026-78669 and CVE-2026-78661 in `.trivyignore-mcp-server` for 3 days, to 2026-11-20. Each reason names the missing fix, the renewal issue #6079 and the tracking issue #6084 of the kubectl bump. The first entries are from 2026-11-08, so the limit of 14 days in all is 2026-11-22.
- The change has no spec delta and sets `skip_specs: true`: it changes only the configuration of a scanner. The requirements of `mcp-server-image` stay true.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `.trivyignore-mcp-server`, which the scan of the `mcp-server` image reads in CI and in the release.
- No tool pin, no image content and no path under `k8s/` changes.

## Feasibility

Read on 2026-11-17 against `origin/main` at `04e1a8b20`.

- `uv run pytest tests/invariants/test_mcp_server_image.py` on the base: 1 failed, 13 passed. The failure names `CVE-2026-56851 expired on 2026-11-17` and two more lines of the same kind.
- The log of the failed job `MCP Server Image` of run 43983603905 (Trivy v0.76.2) has one finding: CVE-2026-56851 in golang.org/x/text v0.40.0, fixed in 0.41.0. CVE-2026-78669 stays hidden there by the entry of `.trivyignore-tofu` (to 2026-11-18), and CVE-2026-78661 by the gh entry of `.trivyignore` (to 2026-11-21).
- `https://dl.k8s.io/release/stable.txt` and `stable-1.37.txt` give v1.37.2. `devops gh api repos/kubernetes/kubernetes/releases`: v1.37.2, v1.36.6, v1.35.10 and v1.34.13 (all 2026-10-28) are the newest stable releases, and v1.38.0-beta.0 (2026-11-06) is a pre-release.
- `go.mod` of kubernetes/kubernetes: v1.37.2 and the branch `release-1.37` hold golang.org/x/net v0.57.0 and golang.org/x/text v0.40.0. v1.36.6 holds x/net v0.56.0 and x/text v0.39.0. Only v1.38.0-beta.0 and `master` hold x/net v0.62.0 and x/text v0.43.0.
- The Go vulnerability database (`https://api.osv.dev/v1/vulns/<id>`): GO-2026-6629 (CVE-2026-56851) is fixed in x/text 0.41.0, GO-2026-6611 (CVE-2026-78669) in x/net 0.60.0, and GO-2026-6860 (CVE-2026-78661) in x/net 0.62.0. Thus no released kubectl holds a fix, and SECURITY.md "A Finding with No Fix" lets an agent renew each entry.
- Trivy 0.76.2 (DB of 2026-11-16) on the kubectl 1.37.2 linux-amd64 binary, whose digest agrees with `tools.lock`: `trivy rootfs --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1` exits 1 with CVE-2026-78669 and CVE-2026-56851, and exits 0 with `--ignorefile .trivyignore-mcp-server` of this change. This DB does not report CVE-2026-78661 for the binary. Its entry stays, as the requirement of #5582 asks.

## Existing Tool Considered

Trivy and its `.trivyignore` format are the open tools. The change builds no code and deletes no code.
