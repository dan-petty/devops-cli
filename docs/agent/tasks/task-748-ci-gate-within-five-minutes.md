# Task: devops ci Quality Gate Finishes Within Five Minutes (#748)

**Issue**: [#748](https://github.com/dan-petty/devops-cli/issues/748)
**Status**: Done
**Milestone**: v0.2.24
**Priority**: priority/p0-critical
**Scope**: scope/ci

## Description
The pre-push gate took 8 to 8.5 minutes against a 5-minute budget, and its time is its pytest-and-coverage step. Measured causes:

- The workspace was checked out on a 9p share of a Windows folder, where a `stat` takes about 400µs against 0.8µs on ext4. The same code and command ran the test step in 518s there and 158s on an ext4 clone.
- `test_trivy_dry_run`, `test_kubelinter_dry_run` and `test_pluto_dry_run` never enabled dry-run mode, so they ran the real scanners over the whole workspace until their 120s and 60s timeouts, then passed on an empty result.
- The network guard blocked connections but not name resolution, so blocked HTTP retries and the reference extractor still made real DNS lookups on every xdist worker.

## Acceptance Criteria
- [x] The full `devops ci --check --no-cache` gate passes in 2m 4s on an ext4 clone (16 cores, 8 pytest workers).
- [x] No tests are dropped: 6,260 pass and 8 xfail, against 6,250 and 8 before the 10 new tests.
- [x] The gate warns when its root is on a 9p or drvfs share, and names the fix.
- [x] When the test step runs past the 5-minute budget, the gate warns and lists pytest's 10 slowest tests.

## Deliverables
- [x] The session network guard fails external DNS lookups with `socket.gaierror`; loopback names and IP literals still resolve.
- [x] A `public_dns` fixture for the 15 tests whose code checks that a URL resolves to a public address.
- [x] The secops dry-run tests enable dry-run mode and assert the simulated finding.
- [x] `devops_cli.ci.diagnostics`: slow-mount detection and durations-report parsing, used by `devops ci`.
- Follow-ups filed separately: tests that write to the project's config and data (#749), and the reference extractor's per-token disk checks (#750).
