# Design

## Decisions

- Delete the three tests. Trivy drops an entry from 00:00 UTC of its `exp:` date, so the image scan is the check of the date. A second check in Tests & Coverage only makes unrelated pull requests fail.
- Remove "Each MCP ignore entry stays valid" and add no requirement. openspec/config.yaml gives a change that only deletes tests no new requirement. The delta exists only because the scenario of the old requirement names a deleted test.
- Do not state that one ignore file sets the date of its finding. Each trivy-action step joins the files of its `trivyignores` input, and Trivy hides a finding while one entry of the same ID is valid. `CVE-2026-78661` and `CVE-2026-78669` are in `.trivyignore-mcp-server` and in `.trivyignore-tofu` with different dates.
- Keep `tests/support/trivyignore.py` and its unit tests in this change. The stale-entry test and the unit tests go in a separate item.

## Rejected alternatives

- Renew the `exp:` dates. Rejected: the tests fail again on the next date, and a renewal needs a reason that the scan accepts (SECURITY.md "A Finding with No Fix"). #4336 and #5573 did this before, and the failure came back.
- Give the tests a fixed date in place of the wall clock. Rejected: the test still only checks a value of a committed config file, which the owner rule of 2026-11-16 forbids. Trivy already enforces the date.
- Mark the tests as skipped after the date. Rejected: that is an escape from a check, and AGENTS.md forbids it.
