# Proposal: #6381

## Why

Three tests read the wall clock and fail on the `exp:` date of a Trivy ignore entry (#6381). Tests & Coverage is a required check. Thus each pull request fails from the date of the first entry, also when it changes no image. The `.trivyignore-mcp-server` entries end on 2026-11-20, and the `.trivyignore-tofu` entries end on 2026-11-21. Trivy already drops an expired entry, so the image scan reports the finding again from the last `exp:` date of its ID and gives the reminder (SECURITY.md "A Finding with No Fix"). The owner rule of 2026-11-16 forbids a test that only checks a value of a config file.

## What Changes

- Delete the three tests that call `trivyignore_problems(text, datetime.now(UTC).date())`:
  - `tests/invariants/test_mcp_server_image.py`: the test of `.trivyignore-mcp-server`.
  - `tests/invariants/test_runner_image.py`: the test of `.trivyignore-tofu`.
  - `tests/invariants/test_service_image.py`: the test of `.trivyignore`.
- Lower the counts of the three modules in `tests/gate/tree_checks/config_reads.toml` to match.
- Keep `tests/support/trivyignore.py`, because the unit tests of the helper in `tests/invariants/test_service_image.py` still use it.
- Keep the assertions on the trivy-action inputs (severity, ignore-unfixed, exit-code). They wait for an owner decision (#6060).
- Remove the requirement "Each MCP ignore entry stays valid". The change alters no behavior that a consumer observes, so it adds no requirement. It has a spec delta only because the scenario of that requirement names a test that this change deletes.

## Capabilities

- Modified: `mcp-server-image` (removes "Each MCP ignore entry stays valid").

## Impact

- Tests & Coverage stops to fail on the `exp:` date of an ignore entry.
- The image scans of `ci.yml` and `release.yml` still report a finding again when no ignore entry of its ID stays valid. Each trivy-action step joins the files of its `trivyignores` input into one ignore file, and Trivy hides a finding while one entry with the same ID is not expired. Trivy reads an `exp:` date as 00:00 UTC of that day. Thus the scan reports the finding from the last `exp:` date of that ID in the joined files. For example, `CVE-2026-78661` has `exp:2026-11-20` in `.trivyignore-mcp-server` and `exp:2026-11-21` in `.trivyignore-tofu`, so the MCP Server Image scan reports it from 2026-11-21.
- No change under `src/`, no manifest and no workflow.

## Feasibility

- Trivy v0.76.2 source, `pkg/result/ignore.go`: `Prune` (lines 131-141) skips a finding when `ExpiredAt.Before(clock.Now(ctx))`. `ParseIgnoreFile` calls `Prune` on each list (lines 249-252). `parseIgnore` reads the `exp:` field into `ExpiredAt`.
- Command output, Trivy 0.76.2 with the local database: `trivy fs --scanners vuln --exit-code 1 --ignorefile <file>` on a `requirements.txt` with `requests==2.19.0`. The entry `CVE-2018-18074 exp:2026-11-18` gives exit 1 and reports the finding. The entry `CVE-2018-18074 exp:2026-11-20` gives exit 0. The entry `CVE-2018-18074 exp:2026-11-18` followed by `CVE-2018-18074 exp:2026-11-21` hides the finding. The entry `CVE-2018-18074 exp:2026-11-19` gives exit 1 and reports the finding. The test date was 2026-11-19.
- `.github/workflows/ci.yml:758` gives `trivyignores: .trivyignore,.trivyignore-mcp-server,.trivyignore-tofu` to the MCP Server Image step. The `entrypoint.sh` of aquasecurity/trivy-action v0.36.0 appends each file to one ignore file and sets `TRIVY_IGNOREFILE` to it.
- `git grep -n 'datetime.now' -- tests/invariants/test_*_image.py` finds the three tests, at `test_mcp_server_image.py:91`, `test_runner_image.py:120` and `test_service_image.py:190`.

## Existing Tool Considered

Trivy itself enforces the `exp:` date of an ignore entry, so the change keeps no code of its own for it. The change deletes three tests and builds nothing. `tests/support/trivyignore.py` stays for its unit tests in `tests/invariants/test_service_image.py`, which a later item removes.
