# Proposal

## Why

Issue #3920 asks for a gh pin whose golang.org/x/net fixes CVE-2026-78661 (HIGH) and for the end of the time-limited ignore. The staged tree already pins v2.105.0 and the Service image reads no ignore, but the invariant test still names the floor of v2.102.1 and the three findings of the older build, so a downgrade or a new ignore passes it.

## What Changes

- Raise `GH_FIRST_SAFE_VERSION` in `tests/invariants/test_service_image.py` to `Version("2.105.0")`, the first cli/cli release whose `go.mod` holds golang.org/x/net 0.62.0, and rewrite its comment and the docstring of the test that reads it.
- Add `CVE-2026-78661` to `GH_GO_FINDINGS_FIXED_IN_THE_PIN` in the same module and rewrite its comment, so the invariant test rejects an ignore of that finding in `.trivyignore`.
- Change no version, no checksum and no install path: `Dockerfile` already fetches gh v2.105.0, and the `GH_VERSION` pin of the runner tools module already holds `2.105.0`.
- Keep the `CVE-2026-78661` entry in `.trivyignore-tofu` for promtool v3.16.0 and OpenTofu v1.13.9, and leave its removal to #6389 after #6365 and #5866.
- No spec delta: every changed path is under `tests/`, and the change alters only the invariant test that reads committed files, so no consumer-visible behavior changes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/invariants/test_service_image.py`

## Feasibility

- The premise of the issue fails at the staging commit: the Dockerfile already pins the safe release, so no bump is left to build. The two asset URLs are `Dockerfile:45:url="https://github.com/cli/cli/releases/download/v2.105.0/gh_2.105.0_linux_amd64.tar.gz"` and `Dockerfile:48:url="https://github.com/cli/cli/releases/download/v2.105.0/gh_2.105.0_linux_arm64.tar.gz"`, and the install step takes the same version at `Dockerfile:55:install -m 755 "/tmp/gh_2.105.0_linux_${TARGETARCH}/bin/gh" /usr/local/bin/gh`.
- `src/devops_cli/roadmap/runner_tools.py:44:GH_VERSION = "2.105.0"` matches that pin, so the statement of the issue that the image pins v2.102.1 is out of date.
- The Service image reads no ignore now: `.trivyignore` has 5 lines and each one is a comment, and its line `.trivyignore:3:The scans of the Service, runner and MCP server images read this file.` names the scans that read it.
- The entry that the issue asks to drop still exists, so that part cannot be built: `.trivyignore-tofu:27:CVE-2026-78661 exp:2026-11-21`, under the reason `.trivyignore-tofu:23:x/net v0.61.0 in promtool v3.16.0 and v0.57.0 in OpenTofu v1.13.9`. Only the Runner Image and MCP Server Image scans read that file, at `.github/workflows/ci.yml:649:trivyignores: .trivyignore,.trivyignore-tofu`, and the Service Image step names no `trivyignores` input at `.github/workflows/ci.yml:522:Scan Service Image for Vulnerabilities`. #6365 and #5866 are open and wait on upstream releases, and #6389 carries the removal, so this plan removes nothing there.
- The work that is left is the two constants of the invariant test: `tests/invariants/test_service_image.py:27:GH_FIRST_SAFE_VERSION = Version("2.102.1")` and `tests/invariants/test_service_image.py:31:GH_GO_FINDINGS_FIXED_IN_THE_PIN = frozenset({"CVE-2026-78667", "CVE-2026-97031", "CVE-2026-78669"})`.
- The `references` tool counted one file for each constant: `GH_FIRST_SAFE_VERSION` gave files 1, lines 2, at `tests/invariants/test_service_image.py` lines 27 and 127, and `GH_GO_FINDINGS_FIXED_IN_THE_PIN` gave files 1, lines 2, at lines 31 and 142, so no other file names either constant.
- The probe lines confirm the cited paths: The path `tests/invariants/test_service_image.py` is a file of the staging commit. The path `.github/renovate.json` is a file of the staging commit. The path `go.mod` that the issue names is no file of the staging commit, because it is the file of another repository, and no tool of this run reads it.
- The premise that v2.105.0 vendors golang.org/x/net 0.62.0 is not checked by this run: no tool here reaches GitHub. The check of the person on 2026-11-19 in the issue comment records Go 1.27.4 and golang.org/x/net 0.62.0 for that release, after v2.104.0 with 0.61.0.
- The first check of the implementation is `uv run devops ci test tests/invariants/test_service_image.py`; it needs a checkout of the repository, no client and no network. The real-system checks that follow run on the pull request: the `Service Image` job at `.github/workflows/ci.yml:522:Scan Service Image for Vulnerabilities` and the `Runner Image` job at `.github/workflows/ci.yml:640:Scan Runner Image for Vulnerabilities`.
- The plan introduces no program and no runner capability: `uv run devops ci test` is an existing row, and `uv` and `pytest` are entries of `src/devops_cli/roadmap/runner_tools.py:94:RUNNER_TOOLS: tuple[RunnerTool, ...] = (`, while no `NOT_IN_RUNNER` program is needed. The only failure class is a failing pytest run, and the test writes no file, so the read-only root of the runner pod is no obstacle.
- The date 2026-11-21 stays as it is: this change moves no expiry, and the removal of the runner entry waits on #6365 and #5866 through #6389.

## Existing Tool Considered

renovatebot/renovate (AGPL-3.0, maintained, last activity 2026-11-08) is the open tool that covers part of the need: it proposes a newer gh release in the Dockerfile from `.github/renovate.json`, but it cannot read a candidate release's go.mod or move `GH_FIRST_SAFE_VERSION` and `GH_GO_FINDINGS_FIXED_IN_THE_PIN`, so this change updates the two test constants by hand and builds no tool.

## Dependencies

- Pull request #6166 shares `src/devops_cli/roadmap/runner_tools.py` with this item; this plan reads `GH_VERSION` there and changes nothing in it, so the two do not conflict.
- Pull request #6390 shares `tests/invariants/test_service_image.py`; it deletes the Trivy ignore tests that read the clock, and this plan leaves those tests alone while it edits the floor and the fixed set.
