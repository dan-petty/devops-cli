# Tasks

## 1. A lookup that did not succeed is never an ok record

- [ ] 1.1 Write the failing tests in `tests/test_vulnerability_lookup.py` and `tests/test_security_threat_intel.py` (a failed lookup, a rate limit, the answered lookups, the review, the tool reply, the required outcome and a cached record with no outcome), and verify that they fail on the base with `uv run devops ci fail-to-pass --base origin/main`
- [ ] 1.2 Make `NetworkReputationRecord.outcome` required with the type `LookupOutcome`, give the InternetDB client its outcomes and its `ok`-only cache, name the outcome in the Radar records, the review fallbacks and the `security_intel_network` reply, and verify with `uv run devops ci test tests/test_vulnerability_lookup.py tests/test_security_threat_intel.py tests/test_builtin_tools.py tests/test_review_pipeline.py`
- [ ] 1.3 Name the outcome in each record that the other tests build, and verify with `uv run devops ci test tests/test_osv_scanner.py tests/test_review_console_report.py tests/test_review_finding_losses.py tests/review/test_report.py`

## 2. Archive

- [ ] 2.1 Archive the change with `uv run devops openspec archive 2504-shodan-failed-lookup-outcome`

## Workflow follow-up

- Pending a person: review the diff.
