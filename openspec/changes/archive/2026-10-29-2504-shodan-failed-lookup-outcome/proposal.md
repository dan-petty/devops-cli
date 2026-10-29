# Proposal

## Why

Issue #2504: a failed Shodan InternetDB lookup gives a record with the outcome `ok`.
The model gives `outcome` the default `ok`, and the failure branch of `ShodanInternetDBClient.check_ip` sets only a summary.
The client also keeps the failed record, so it never asks about the address again.
The review shows "Unchecked" only for the outcomes `unavailable` and `failed`, so it shows the address as "✓ Safe / Low Risk".
#1429 fixed the same defect for Cloudflare Radar.
A failed lookup must never read as verified.

The default `ok` is the cause, and it hides more than one branch:

- A reply of 429, 500 or 422 from InternetDB also gives `ok` with the summary "Clean".
- A reply of 200 or 404 gives `ok` by its status alone. A proxy that answers 200 with `{}`, or 404 with an HTML page, shows every address as safe.
- A fallback record of the review is `ok` when no lookup answered a reference, as in a dry run.
- The `security_intel_network` reply says "None detected" for the ports and CVEs of a failed Shodan lookup. For a failed Radar lookup, it says "Threat Categories: None".
- A reference that no lookup checked ranks below a safe one in the report. So a "Safe" row hides an "Unchecked" row of the same target.
- A Valkey entry written before records had an outcome would read as `ok`.

This change fits one pull request.

## What Changes

- `NetworkReputationRecord.outcome` has no default. Its type is `LookupOutcome`: `ok`, `unavailable` or `failed`. Each client names the outcome of each record. A cached record with no outcome is a cache miss.
- The InternetDB client checks the body of a reply with pydantic models. A 200 body must hold `ip`, `ports` and `vulns`. A 404 body must hold the `detail` "No information available".
- The InternetDB client gives `ok` for a reply with such a body. It gives `unavailable` for a 429 and for a domain. It gives `failed` for any other reply and for any error.
- The InternetDB client keeps `ok` records only, so a call after a failed one asks again.
- A review gives a reference that no lookup answered the outcome `unavailable`, and shows it as "Unchecked".
- The two helpers of the review that caught every error of a lookup client are deleted. No public call reaches that code.
- The tool reply for a failed or unavailable lookup gives the summary only. This holds for an address (Shodan) and for a domain (Radar).
- An "Unchecked" reference ranks after the flagged and the medium ones and before every safe one. It is yellow in the report and in the table.
- The Radar client keeps its behavior. Its records name their outcome, and the dead second `return` of `_query_radar_http` goes.
- The change alters what a review and a tool reply show, so it carries a spec delta.

## Capabilities

### New Capabilities

- `threat-intel-lookup-outcome`: how a threat-intelligence record names the end of its lookup, and how the review and the tools show a lookup that did not succeed.

## Impact

- `src/devops_cli/models/vulnerability.py`
- `src/devops_cli/security/vulnerability_lookup.py`
- `src/devops_cli/security/reference_extractor.py`
- `src/devops_cli/ai/review/pipeline.py`
- `src/devops_cli/ai/tools/builtin_tools.py`
- `src/devops_cli/review/report.py`
- `src/devops_cli/output/formatters/tables.py`
- `tests/test_vulnerability_lookup.py`
- `tests/test_security_threat_intel.py`
- `tests/security/test_reference_report_order.py`
- `tests/test_review_console_report.py`
- The tests that build a `NetworkReputationRecord`: `tests/test_builtin_tools.py`, `tests/test_osv_scanner.py`, `tests/test_review_finding_losses.py`, `tests/test_review_pipeline.py`, `tests/review/test_report.py`

## Feasibility

- **The defect, on `origin/main` at dde2f55b.** An offline probe made `socket.getaddrinfo` answer `10.0.0.1` for `internetdb.shodan.io`. It used `scripted_resolver` and `record_connects` from `tests/web_fakes.py`. The probe called `ShodanInternetDBClient().check_ip("93.184.215.14")` twice.
- **The result of the probe.** It printed `outcome: ok | summary: Unchecked / Lookup timeout` and `cached: True`, with one DNS lookup for the two calls. The pipeline then gives "✓ Safe / Low Risk" (`_determine_network_security_status`).
- **The reply statuses.** The OpenAPI document of InternetDB (`https://internetdb.shodan.io/openapi.json`) lists the statuses 200 and 422 for `GET /{ip}`. A live request for `192.0.2.1` got 404, and the client already reads 404 as "no data". The document names no rate limit. The 429 branch follows RFC 6585 and the Radar client, which maps 429 to `unavailable`.
- **The reply bodies.** A live request on 2026-10-29 for `1.1.1.1` got 200 with the keys `cpes`, `hostnames`, `ip`, `ports`, `tags` and `vulns`. The request for `192.0.2.1` got the body `{"detail":"No information available"}`. FastAPI answers a missing route with `{"detail":"Not Found"}`, so the 404 check must name the exact text.
- **The model.** pydantic 2.13.5 refuses a missing field and a value outside a `Literal`. `CloudflareRadarClient._get_from_valkey_l2` already treats a validation error as a miss.
- **The sites that the default hid.** A required field shows each place that builds a record with no outcome. There are five in `src/`. They are the InternetDB records, the Radar record of an unasked target, and the Radar record at the start of `_query_radar_http`. The other two are the fallback records of the review. Only the InternetDB records and the review fallbacks gave a wrong outcome.
- **The loaders of `findings.json`.** Four readers call `ReviewSessionPayload.model_validate_json` with no shared loader. Design.md records the effect on old files.

## Existing Tool Considered

pydantic, which the project already uses, enforces the outcome with a required `Literal` field. It also checks the two reply bodies. The change adds no parser, no helper and no dependency.
The change deletes the model default `ok`, the cached failed record and the summary "Unchecked / Lookup timeout". It also deletes the default record for a reference that no lookup answered. It deletes the two broad fallbacks of the review. It deletes the unreachable second `return record, cacheable` in `_query_radar_http`.
