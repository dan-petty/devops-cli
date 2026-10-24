# Proposal

## Why

Issue #916: A Gitleaks scan on a file list dropped start and end timestamps from the merged outcome. The fix merged in release v0.2.25, but no test verified the behavior.

## What Changes

- Add a unit test in `tests/test_scan_outcomes_and_gating.py` to assert that `merge_outcomes` preserves the earliest start time and the latest end time across merged scan outcomes.
- Add an integration test in `tests/test_security_gitleaks.py` to assert that a two-file list scan with a mocked Gitleaks subprocess records both start and end times in the SARIF invocation.
- Assert that the start time is earlier than or equal to the end time in the SARIF output.

This change alters no behavior that an external consumer observes. The implementation was completed in release v0.2.25 and this change adds regression tests. The change sets `skip_specs: true` in `.openspec.yaml`.

This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `tests/test_security_gitleaks.py`: Add test verifying that a two-file list scan keeps start and end times in the SARIF invocation.
- `tests/test_scan_outcomes_and_gating.py`: Add test verifying that `merge_outcomes` calculates the earliest start time and latest end time.

## Feasibility

I confirmed the premise against the code and test suite:
- Inspected `src/devops_cli/security/base.py` lines 142-144. `merge_outcomes` computes `min(starts)` and `max(ends)` and assigns them to `merged.started_utc` and `merged.ended_utc`.
- Inspected `src/devops_cli/security/gitleaks.py` line 142. `GitleaksScanner.scan` passes per-file outcomes to `merge_outcomes`.
- Inspected `src/devops_cli/security/sarif.py` lines 257 and 201-208. `to_sarif` maps `started_utc` and `ended_utc` to `startTimeUtc` and `endTimeUtc` in the run invocation.
- Verified in git history that commit 79119417 (release v0.2.25) added the time-retention logic to `merge_outcomes`, but did not add a regression test for list scans with Gitleaks.

## Existing Tool Considered

The test suite uses `pytest` and `unittest.mock`. The SARIF export logic uses the internal `devops_cli.security.sarif` module conforming to the OASIS SARIF 2.1.0 standard. No new external tool is needed.
