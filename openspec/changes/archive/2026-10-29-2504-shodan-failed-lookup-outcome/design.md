# Design

## The outcome of a lookup that did not succeed

The InternetDB client gives `failed` for an error and for each status other than 200, 404 and 429.
An error is a timeout, a failed connect, a refused DNS answer or a body that does not match.
It gives `unavailable` for 429.
This is the mapping of `CloudflareRadarClient`, and the pipeline already shows both outcomes as "Unchecked".

Each record is built with its final outcome, in one place for each reply.
The old code built one record up front and let the branches change it, so a branch that forgot left the default.

### Rejected alternatives

- **`unavailable` for every failure.** Rejected: `unavailable` means the service could not answer, as with a rate limit or a missing token. A connect error or a server error is a failure, and `OSVClient` and Radar name it `failed`.
- **`ok` for a status other than 200 and 404.** Rejected: this is the defect. An answer of 500 would read as "Clean".

## The body of a reply

A status does not make a reply an InternetDB reply.
A proxy, a CDN or a changed route can answer 200 with `{}`, or 404 with an HTML page.
The client parses the body with two pydantic models in `models/vulnerability.py`.
`InternetDBHost` needs `ip`, `ports` as integers and `vulns` as text, and keeps `tags` and `hostnames`.
`InternetDBNoData` needs the `detail` "No information available".
A body that does not match gives `failed`, and the client does not keep it.

The check of the 404 body names the exact text.
FastAPI, which serves InternetDB, answers a missing route with `{"detail":"Not Found"}`, so any `detail` text would accept a changed route.
If Shodan changes its text, the lookup fails safe and the review shows "Unchecked".

### Rejected alternatives

- **Trust the status.** Rejected: this is the defect of the section above, shown by the probe of a 200 with `{}`.
- **A hand-written parser or key checks.** Rejected: pydantic already validates the shape and the types, and the project uses it for every reply.
- **Any `detail` text for a 404.** Rejected: it accepts `{"detail":"Not Found"}` from a missing route.
- **Check that `ip` equals the address asked.** Rejected: IPv6 addresses have more than one spelling, so the check could fail a good reply.

## The cache of a failed record

The client keeps `ok` records only.
A call after a failed or unavailable one asks again.

`OSVClient` also keeps no failed lookup.
Radar keeps a failed record in its memory tier, where each record expires after the TTL, and does not write it to Valkey.
The InternetDB cache is a plain `dict` with no expiry, so a kept failed record would hide its address for the life of the client.
That is the second effect of #2504.
A retry costs one request with a connect timeout of 1 s.

Radar stays as it is.
Its memory tier expires, and a client lives for one review or one tool call.

### Rejected alternatives

- **Keep a failed record with an expiry, as Radar does.** Rejected: it needs a TTL cache and a clock seam in a client that has none. The gain is nil, because the review asks each address one time (`unique_nets`).
- **Keep all records.** Rejected: this is the defect.

## The default of `outcome`

`outcome` is a required field of type `Literal["ok", "unavailable", "failed"]`, named `LookupOutcome`.

#1429 added the field with the default `ok`, and the InternetDB client then missed it.
A required field turns the next miss into an error at the first test run, at the line that builds the record.
It also made the old default visible: five sites in `src/` relied on it.

- The InternetDB records.
- The Radar record of an unasked target.
- The Radar record at the start of a lookup.
- The fallback record of an address client that raises.
- The fallback record of a reference that has no record.

A cached record with no outcome now fails validation.
`_get_from_valkey_l2` treats a validation error as a cache miss, so Radar asks again.
Such a record comes from before #1429, and it could carry a synthetic "verified" summary.

### Rejected alternatives

- **The default `unavailable`.** Rejected: a forgetful client would show "Unchecked" with no error. A cached record with no outcome would be served as unchecked and never asked again.
- **Keep the default `ok` and fix the client.** Rejected: #1429 did this for Radar, and the same defect came back in the next client.
- **A `StrEnum`.** Rejected: pydantic validates a `Literal` with no new class, and the project already types statuses this way (`DiveStatus`).

## Old session files

`ReviewSessionPayload` holds `NetworkReference.reputation`, so a `findings.json` written before #2289 has records with no `outcome`.
Such a file no longer loads.
This is the choice of this change: a pre-1.0 release keeps no old path, and a default `ok` would show an unchecked address as safe.

Four readers load the file, and each calls `ReviewSessionPayload.model_validate_json` itself.
They are the findings list, `_read_session_file` and `_session_findings` in `commands/review.py`, and `read_session` in `review/handoff.py`.
No single loader serves them, so one handler in one place cannot cover them.
Each reader ends with a pydantic traceback, with no file name.
This is true for every schema change, so it is an item of its own: #2644.

## The review

`_audit_file_network_references` gives a reference with no record the outcome `unavailable`.
This happens in a dry run, where `_fetch_threat_intel` returns no record.

The review had two helpers, `_fetch_ip_threat_intel` and `_fetch_domains_threat_intel`, with a broad `except Exception` that built a fallback record.
No public call reaches that code.
`ShodanInternetDBClient.check_ip` catches every error of its request itself.
`CloudflareRadarClient.check_domains_batch` catches the error of each domain, and the Valkey tier fails soft.
Only a patch of the client made the fallbacks run, and a broad catch hides a real defect.
This change deletes the fallbacks.
`_fetch_domains_threat_intel` is gone, and `_fetch_ip_threat_intel` only pairs the address with its record.

The order of the checks in `_determine_network_security_status` stays: malicious, then an outcome that is not `ok`, then example, local, ports and safe.
So a dry run shows every reference as "Unchecked", also a local one.

### Rejected alternatives

- **Keep the fallbacks and test them with a patch.** Rejected: docs/TESTING.md allows no new patch of devops-cli and no private import, and it says to delete code that no public behavior reaches.
- **Check example and local before the outcome.** Rejected: where the reference flags and `classify_network_target` disagree, a failed lookup of a reference flagged local would show "Safe (Local)". A dry run that shows "Unchecked" for a local reference is true, because nothing ran.

## Targets that InternetDB does not take

A documented example or a local address gets an `ok` record with its summary and no request, as Radar gives for the same classes.
What the address is says all there is to say, and the review shows it by the reference flags.
A domain gets `unavailable`, because InternetDB takes addresses only.
The cache holds neither the domain nor any other record that is not `ok`.

## The tool replies

For `unavailable` and `failed`, the reply of `security_intel_network` gives the summary only.
It never says "None detected" for ports or CVEs that nobody read, and it never says "Threat Categories: None" for a domain that Radar did not check.
The Radar reply printed that line before this change.

## The rank of an unchecked reference

`_network_security_severity_rank` gave "Unchecked" the rank 5, below "Safe".
`deduplicate_network_references` keeps the lowest rank of one target, so a "Safe" row hid an "Unchecked" row.
The rank of "Unchecked" is now 3: after the flagged and medium statuses, and before "Low Risk" and "Safe".
The report and the table also color an unchecked reference yellow.

### Rejected alternatives

- **Keep "Unchecked" last.** Rejected: an address that nobody checked must not show as safe, and the table lists the most severe row first.
- **Rank "Unchecked" with the flagged ones.** Rejected: nothing found a defect in it. It needs a look, and it is not a finding.

The table of `format_network_references_table` colors a "Safe / Low Risk" status red, because the status holds the text "RISK".
That defect is older than this change and has its own item: #2646.

## Not in this change

`PackageLookupResult.status` has the default `ok` too, `NetworkReference.security_status` defaults to "✓ Safe", and `NetworkIntelResult` and `PackageIntelResult` default to "Safe" and "Clean".
The review replaces the status of each reference, and every constructor of `PackageLookupResult` names its status today.
The two intel models have no user in `src/`.
So none of them gives a wrong result today.
#2636 holds them.

## Tests

- `test_shodan_lookup_that_did_not_succeed_is_no_ok_record` runs twelve cases with `scripted_resolver` and `record_connects`. They are a refused private answer, a failed connect, 500, 422, 429, and six replies with a body that is not from InternetDB. Each case checks that the next call asks again.
- `test_shodan_answered_lookup_is_ok_and_asked_once` holds 200 and 404 with the right body as `ok` and kept.
- `test_review_shows_a_failed_shodan_lookup_as_unchecked` and `test_review_shows_a_reference_that_no_lookup_answered_as_unchecked` run `init_per_file_payloads` with threat intelligence on.
- `test_tool_reply_of_a_failed_shodan_lookup_names_no_result` and the Radar error test cover the tool replies.
- `test_reputation_record_needs_a_known_outcome` and `test_a_threat_intel_entry_with_no_outcome_is_a_miss` cover the model and the cached record.
- `tests/security/test_reference_report_order.py` and `tests/test_review_console_report.py` cover the rank, the merge and the color.
