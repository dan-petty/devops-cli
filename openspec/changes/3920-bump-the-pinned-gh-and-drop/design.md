# Design

## Decisions

- **Set `GH_FIRST_SAFE_VERSION` to `Version("2.105.0")`.**: The pin is v2.105.0, the first cli/cli release with golang.org/x/net 0.62.0 (the person's check of 2026-11-19 records v2.104.0 with 0.61.0 before it), so the floor now rejects every pin that brings CVE-2026-78661 back.
- **Add `CVE-2026-78661` to `GH_GO_FINDINGS_FIXED_IN_THE_PIN`.**: The test rejects an ignore for a finding that the pinned build fixes, and the Service image scan reads `.trivyignore` only, so a later ignore there fails the test instead of hiding the finding again.
- **Leave the `CVE-2026-78661` entry in `.trivyignore-tofu` and defer its removal to #6389.**: promtool v3.16.0 and OpenTofu v1.13.9 are the newest releases and still vendor x/net 0.61.0 and 0.57.0, and only the Runner Image and MCP Server Image scans read that file, so the Service image scan needs no entry and the runner scan still needs this one.
- **Keep the manual pin and the invariant update, and add no Renovate rule.**: The alternatives check of 2026-11-09 records the verdict partly: Renovate proposes a newer release in the Dockerfile but cannot read a candidate release's go.mod or move the Python constants, so the floor and the fixed set stay manual.

## Rejected alternatives

- **Keep the floor at 2.102.1.**: `tests/invariants/test_service_image.py:27:GH_FIRST_SAFE_VERSION = Version("2.102.1")` accepts a pin at 2.102.1 or 2.104.0, which vendor golang.org/x/net 0.60.0 and 0.61.0, so the test would pass with the finding back.
- **Remove the `CVE-2026-78661` entry from `.trivyignore-tofu` now.**: `.trivyignore-tofu:23:x/net v0.61.0 in promtool v3.16.0 and v0.57.0 in OpenTofu v1.13.9` shows that both newest releases still vendor the older module, and the Runner Image scan reads that file at `.github/workflows/ci.yml:649:trivyignores: .trivyignore,.trivyignore-tofu`, so its scan would fail.
- **Bump gh to a release newer than v2.105.0.**: The staged tree already pins v2.105.0 at `Dockerfile:45:url="https://github.com/cli/cli/releases/download/v2.105.0/gh_2.105.0_linux_amd64.tar.gz"` and at `src/devops_cli/roadmap/runner_tools.py:44:GH_VERSION = "2.105.0"`, so a further bump is a dependency update outside this item.
- **Add a Renovate custom manager for the gh release URL.**: The alternatives check of 2026-11-09 records that Renovate cannot choose the first release whose go.mod holds x/net 0.62.0, cannot move `GH_VERSION` or the floor, and cannot check the scans, so the rule would cover the Dockerfile line alone.
