# Proposal: #6381

## Why

Three tests read the wall clock and fail on the `exp:` date of a Trivy ignore entry (#6381). Tests & Coverage is a required check. Thus each pull request fails from the date of the first entry, also when it changes no image. The `.trivyignore-mcp-server` entries end on 2026-11-20, and the `.trivyignore-tofu` entries end on 2026-11-21. Trivy already drops an expired entry, so the image scan fails after the date and gives the reminder (SECURITY.md "A Finding with No Fix"). The owner rule of 2026-11-16 forbids a test that only checks a value of a config file.

## What Changes

- Delete the three tests that call `trivyignore_problems(text, datetime.now(UTC).date())`:
  - `tests/invariants/test_mcp_server_image.py`: the test of `.trivyignore-mcp-server`.
  - `tests/invariants/test_runner_image.py`: the test of `.trivyignore-tofu`.
  - `tests/invariants/test_service_image.py`: the test of `.trivyignore`.
- Lower the counts of the three modules in `tests/gate/tree_checks/config_reads.toml` to match.
- Keep `tests/support/trivyignore.py`, because the unit tests of the helper in `tests/invariants/test_service_image.py` still use it.
- Keep the assertions on the trivy-action inputs (severity, ignore-unfixed, exit-code). They wait for an owner decision (#6060).
- Replace the requirement "Each MCP ignore entry stays valid" with "An expired MCP ignore entry stops hiding its finding". The MCP Server Image scan is its proof, not a test that reads the file. The change alters no behavior that a consumer observes. It has a spec delta only because the current scenario names a test that this change deletes.

## Capabilities

- Modified: `mcp-server-image` (removes "Each MCP ignore entry stays valid" and adds "An expired MCP ignore entry stops hiding its finding").

## Impact

- Tests & Coverage stops to fail on the `exp:` date of an ignore entry.
- The image scans of `ci.yml` and `release.yml` still fail after the `exp:` date of an entry, because Trivy drops the entry and reports the finding again.
- No change under `src/`, no manifest and no workflow.

## Feasibility

- Trivy v0.76.2 source, `pkg/result/ignore.go`: `Prune` (lines 131-141) skips a finding when `ExpiredAt.Before(clock.Now(ctx))`. `ParseIgnoreFile` calls `Prune` on each list (lines 249-252). `parseIgnore` reads the `exp:` field into `ExpiredAt`.
- Command output, Trivy 0.76.2 with the local database: `trivy fs --scanners vuln --exit-code 1 --ignorefile <file>` on a `requirements.txt` with `requests==2.19.0`. The entry `CVE-2018-18074 exp:2026-11-18` gives exit 1 and reports the finding. The entry `CVE-2018-18074 exp:2026-11-20` gives exit 0. The test date was 2026-11-19.
- `git grep -n 'datetime.now' -- tests/invariants/test_*_image.py` finds the three tests, at `test_mcp_server_image.py:91`, `test_runner_image.py:120` and `test_service_image.py:190`.

## Existing Tool Considered

Trivy itself enforces the `exp:` date of an ignore entry, so the change keeps no code of its own for it. The change deletes three tests and builds nothing. `tests/support/trivyignore.py` stays for its unit tests in `tests/invariants/test_service_image.py`, which a later item removes.
