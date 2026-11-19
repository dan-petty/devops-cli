# Design

## Decisions

- Delete the three tests. Trivy drops an entry after its `exp:` date, so the image scan is the check of the date. A second check in Tests & Coverage only makes unrelated pull requests fail.
- Replace "Each MCP ignore entry stays valid" with a requirement whose scenario names the MCP Server Image scan as its proof. openspec/config.yaml forbids a scenario that a test proves by a read of a config file. A MODIFIED delta cannot drop the old scenario, so the delta removes the old requirement and adds the new one.
- Keep `tests/support/trivyignore.py` and its unit tests in this change. The stale-entry test and the unit tests go in a separate item.

## Rejected alternatives

- Renew the `exp:` dates. Rejected: the tests fail again on the next date, and a renewal needs a reason that the scan accepts (SECURITY.md "A Finding with No Fix"). #4336 and #5573 did this before, and the failure came back.
- Give the tests a fixed date in place of the wall clock. Rejected: the test still only checks a value of a committed config file, which the owner rule of 2026-11-16 forbids. Trivy already enforces the date.
- Mark the tests as skipped after the date. Rejected: that is an escape from a check, and AGENTS.md forbids it.
