# Proposal

## Why

Issue #2504: a failed Shodan InternetDB lookup gives a record with outcome `ok`.
`NetworkReputationRecord.outcome` has the default `ok`, and the failure branch of `ShodanInternetDBClient.check_ip` sets only a summary.
The client also keeps the failed record, so it never asks about the address again.
The review shows the address as "✓ Safe / Low Risk", because it shows "Unchecked" only for the outcomes `unavailable` and `failed`.
#1429 fixed the same defect for Cloudflare Radar, and a failed lookup must never read as verified.

The default `ok` is the cause, and it hides more than the one branch:

- An InternetDB reply of 429, 500 or 422 also gives `ok` with the summary "Clean".
- A fallback record of the review is `ok` when a client raises (`_fetch_ip_threat_intel`), and when no lookup answered a reference, as in a dry run (`_audit_file_network_references`).
- The reply of the `security_intel_network` tool says "None detected" for the ports and CVEs of a failed lookup.
- A Valkey entry written before records had an outcome would read as `ok`.

This change fits one pull request.

## What Changes

- `NetworkReputationRecord.outcome` has no default, and its type is `LookupOutcome`: `ok`, `unavailable` or `failed`. Each client names the outcome of each record it builds. A cached record with no outcome is a cache miss.
- The InternetDB client gives `ok` for a 200 and a 404, `unavailable` for a 429, and `failed` for any other status and for any error. A target that InternetDB does not take, a domain, gives `unavailable`. The client keeps `ok` records only, so a call after a failed one asks again.
- The review gives a fallback record `failed` when a client raises, and `unavailable` when no lookup answered a reference. The review shows both as "Unchecked".
- The reply of the `security_intel_network` tool for a failed or unavailable address names the summary only, as the Radar reply does.
- The Radar client keeps its behavior. Its records name their outcome, and the dead second `return` of `_query_radar_http` goes.
- The change alters what a review and a tool reply show, so it carries a spec delta.

## Capabilities

### New Capabilities

- `threat-intel-lookup-outcome`: how a threat-intelligence record names the end of its lookup, and how the review and the tool show a lookup that did not succeed.

## Impact

- `src/devops_cli/models/vulnerability.py`
- `src/devops_cli/security/vulnerability_lookup.py`
- `src/devops_cli/ai/review/pipeline.py`
- `src/devops_cli/ai/tools/builtin_tools.py`
- `tests/test_vulnerability_lookup.py`
- `tests/test_security_threat_intel.py`
- The tests that build a `NetworkReputationRecord`: `tests/test_builtin_tools.py`, `tests/test_osv_scanner.py`, `tests/test_review_console_report.py`, `tests/test_review_finding_losses.py`, `tests/test_review_pipeline.py`, `tests/review/test_report.py`

## Feasibility

- **The defect, on `origin/main` at dde2f55b.** An offline probe made `socket.getaddrinfo` answer `10.0.0.1` for `internetdb.shodan.io` with `scripted_resolver` and `record_connects` (`tests/web_fakes.py`), and called `ShodanInternetDBClient().check_ip("93.184.215.14")` twice. Output: `outcome: ok | summary: Unchecked / Lookup timeout`, `cached: True`, and one DNS lookup for the two calls. The pipeline then gives "✓ Safe / Low Risk" (`_determine_network_security_status`).
- **The reply statuses.** The InternetDB OpenAPI document (`https://internetdb.shodan.io/openapi.json`) lists the statuses 200 and 422 for `GET /{ip}`. A live request for `192.0.2.1` got 404, and the client already reads 404 as "no data". The document names no rate limit, so the 429 branch follows HTTP (RFC 6585) and the Radar client, which maps 429 to `unavailable`.
- **The model.** pydantic 2.13.5 refuses a missing field and a value outside a `Literal`, and `CloudflareRadarClient._get_from_valkey_l2` already treats a validation error as a miss.
- **The sites that the default hid.** A required field shows each place that builds a record with no outcome. There are five in `src/`: the InternetDB records, the Radar record of an unasked target, the Radar record at the start of `_query_radar_http`, and the two fallback records of the review. Only the InternetDB records and the review fallbacks gave a wrong outcome.

## Existing Tool Considered

pydantic, which the project already uses, enforces the outcome with a required `Literal` field. The change adds no helper and no dependency. It deletes the model default `ok`, the cached failed record, the summary "Unchecked / Lookup timeout", the default record for a reference that no lookup answered, and the unreachable second `return record, cacheable` in `_query_radar_http`.
