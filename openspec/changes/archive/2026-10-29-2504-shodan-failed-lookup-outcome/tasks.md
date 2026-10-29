# Tasks

## 1. A lookup that did not succeed is never an ok record

- [x] 1.1 Write the failing tests for the outcomes, the cache, the review and the tool reply. Verify with `uv run devops ci fail-to-pass --base origin/main`.
- [x] 1.2 Make `outcome` required, and give the InternetDB client its outcomes and its `ok`-only cache. Verify with `uv run devops ci test tests/test_vulnerability_lookup.py tests/test_security_threat_intel.py`.
- [x] 1.3 Name the outcome in each record that the other tests build. Verify with `uv run devops ci test tests/test_osv_scanner.py tests/test_review_finding_losses.py tests/review/test_report.py`.

## 2. A reply is ok only with the body of InternetDB

- [x] 2.1 Write the failing tests for a 200 and a 404 with a foreign body. Verify with `uv run devops ci test tests/test_vulnerability_lookup.py`.
- [x] 2.2 Parse the two bodies with pydantic models in the client. Verify with the command of task 2.1.

## 3. The review and the tools name no result for a lookup that did not succeed

- [x] 3.1 Write the failing tests of the Radar reply, and of the rank and the color of an unchecked reference. Verify with `uv run devops ci test tests/security/test_reference_report_order.py tests/test_review_console_report.py`.
- [x] 3.2 Delete the two review fallbacks that no public call reaches. Test the review through `init_per_file_payloads`. Verify with `uv run devops ci test tests/test_vulnerability_lookup.py`.
- [x] 3.3 Drop the category line of the Radar reply. Rank "Unchecked" above "Safe", and color it yellow. Verify with the command of task 3.1.

## 4. Archive

- [x] 4.1 Archive the change with `uv run devops openspec archive 2504-shodan-failed-lookup-outcome`.

## Workflow follow-up

- Model defaults that read as clean (`NetworkReference.security_status`, `PackageLookupResult.status`, `NetworkIntelResult` and `PackageIntelResult`): #2636.
- A `findings.json` that does not validate ends a command with a traceback, so a file written before #2289 does not load: #2644.
- The table of network references colors "✓ Safe / Low Risk" red: #2646.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
