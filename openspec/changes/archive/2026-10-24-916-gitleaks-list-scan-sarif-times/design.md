# Design

## Context

See proposal.md - Why.
`merge_outcomes` merges individual `ScanOutcome` objects into a single outcome. In release v0.2.25, `merge_outcomes` was updated to retain the earliest `started_utc` and latest `ended_utc` timestamps across merged outcomes. When `GitleaksScanner` scans a file list, it delegates to `merge_outcomes`. When devops-cli exports the outcome to SARIF via `to_sarif`, it passes the timestamps to the SARIF run invocation.

## Goals / Non-Goals

**Goals:**
- Pin the behavior of `merge_outcomes` for earliest start and latest end timestamps with a dedicated unit test.
- Verify that a two-file list scan with Gitleaks sets `startTimeUtc` and `endTimeUtc` on the SARIF invocation.
- Assert that `startTimeUtc` is no later than `endTimeUtc`.

**Non-Goals:**
- Modify scanner execution or SARIF formatting logic, because the runtime implementation operates correctly.
- Add real Gitleaks binary execution in tests, because unit tests must remain offline and fast.

## Decisions

### Decision: Test `merge_outcomes` in unit tests and via `run_gitleaks_scan` with `to_sarif`

We test `merge_outcomes` in `tests/test_scan_outcomes_and_gating.py` with explicit ISO-8601 UTC timestamp strings. We test `run_gitleaks_scan` and `to_sarif` in `tests/test_security_gitleaks.py` with a mock subprocess to verify integration without calling a real binary.

*Alternative rejected:* Only test through `run_gitleaks_scan`. Rejected because direct unit tests on `merge_outcomes` isolate timestamp calculations without subprocess mocking overhead.

### Decision: Mock subprocess execution via `patch("devops_cli.security.gitleaks.run_subprocess")`

The Gitleaks integration test uses `unittest.mock.patch` on `devops_cli.security.gitleaks.run_subprocess` to simulate scanner completion.

*Alternative rejected:* Use the recorded runner fixture `scanner_fake`. Rejected because `scanner_fake` matches only single-file recorded invocations and fails on arbitrary multi-file paths.

## Risks / Trade-offs

- [Timestamp ordering errors] → Verify with assertions that `startTimeUtc` is less than or equal to `endTimeUtc`.
