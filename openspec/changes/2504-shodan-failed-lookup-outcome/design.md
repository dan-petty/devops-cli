# Design

## The outcome of a lookup that did not succeed

The InternetDB client gives `failed` for an error (a timeout, a failed connect, a refused DNS answer, a body that is not JSON) and for each status other than 200, 404 and 429. It gives `unavailable` for 429. This is the mapping of `CloudflareRadarClient`, and the pipeline already shows both outcomes as "Unchecked".

Each record is built with its final outcome, in one place for each reply. The old code built one record up front and let the branches change it, so a branch that forgot left the default.

### Rejected alternatives

- **`unavailable` for every failure.** Rejected: `unavailable` means the service could not answer, as with a rate limit or a missing token. A connect error or a server error is a failure, and `OSVClient` and Radar name it `failed`.
- **`ok` for a status other than 200 and 404.** Rejected: this is the defect. An answer of 500 would read as "Clean".

## The cache of a failed record

The client keeps `ok` records only. A call after a failed or unavailable one asks again.

`OSVClient` also keeps no failed lookup. Radar keeps a failed record in its memory tier, where each record expires after the TTL, and does not write it to Valkey. The InternetDB cache is a plain `dict` with no expiry, so a kept failed record would hide its address for the life of the client. That is the second effect of #2504. A retry costs one request with a connect timeout of 1 s.

Radar stays as it is. Its memory tier expires, and a client lives for one review or one tool call.

### Rejected alternatives

- **Keep a failed record with an expiry, as Radar does.** Rejected: it needs a TTL cache and a clock seam in a client that has none, to save one short request after a failure. `cachetools.TTLCache` would do it, but the gain is nil, because the review asks each address one time (`unique_nets`).
- **Keep all records.** Rejected: this is the defect.

## The default of `outcome`

`outcome` is a required field of type `Literal["ok", "unavailable", "failed"]`, named `LookupOutcome`.

#1429 added the field with the default `ok`, and the InternetDB client then missed it. A required field turns the next miss into an error at the first test run, at the line that builds the record. It also made the old default visible: five sites in `src/` relied on it. They are the InternetDB records, the Radar record of an unasked target, the Radar record at the start of a lookup, and the two fallback records of the review.

A cached record with no outcome now fails validation. `_get_from_valkey_l2` treats a validation error as a cache miss, so Radar asks again. Such a record comes from before #1429, and it could carry a synthetic "verified" summary.

### Rejected alternatives

- **The default `unavailable`.** Rejected: a forgetful client would show "Unchecked" with no error, and a cached record with no outcome would be served as unchecked and never asked again. It also keeps a default that says nothing is known, where a record must say how its lookup ended.
- **Keep the default `ok` and fix the client.** Rejected: #1429 did this for Radar, and the same defect came back in the next client.
- **A `StrEnum`.** Rejected: `Literal` is validated by pydantic with no new class, and the project already types statuses this way (`DiveStatus`).

## The review

`_audit_file_network_references` gives a reference with no record the outcome `unavailable`. This happens in a dry run, where `_fetch_threat_intel` returns no record. `_fetch_ip_threat_intel` and `_fetch_domains_threat_intel` give `failed`, with the reason, when a client raises, and they log it.

The order of the checks in `_determine_network_security_status` stays: malicious, then an outcome that is not `ok`, then example, local, ports and safe. So a dry run shows every reference as "Unchecked", also a local one.

### Rejected alternatives

- **Check example and local before the outcome.** Rejected: where the reference flags and `classify_network_target` disagree, a failed lookup of a reference flagged local would show "Safe (Local)". A dry run that shows "Unchecked" for a local reference is true, because nothing ran.

## Targets that InternetDB does not take

A documented example or a local address gets an `ok` record with its summary and no request, as Radar gives for the same classes. What the address is says all there is to say, and the review shows it by the reference flags. A domain gets `unavailable`, because InternetDB takes addresses only. The cache holds neither the domain nor any other not-`ok` record.

## The tool reply

For `unavailable` and `failed`, the reply of `security_intel_network` for an address names the summary only. It never says "None detected" for ports or CVEs that nobody read. `_radar_reply` already does this for a domain.

## Not in this change

`PackageLookupResult.status` has the default `ok` too, and `NetworkIntelResult` and `PackageIntelResult` default to "Safe" and "Clean". Every constructor of `PackageLookupResult` names its status today, and the two intel models have no user in `src/`. Both are filed as separate items.

## Tests

- `test_shodan_lookup_that_did_not_succeed_is_no_ok_record` runs six failures (a refused private answer, a failed connect, 500, 422, a body that is not JSON, and 429) with `scripted_resolver` and `record_connects`, and checks that the next call asks again.
- `test_shodan_answered_lookup_is_ok_and_asked_once` holds 200 and 404 as `ok` and cached.
- `test_failed_shodan_lookup_is_unchecked_in_the_review_and_the_tool`, `test_review_shows_a_reference_with_no_record_as_unchecked` and `test_review_fallback_of_a_client_that_raises_is_failed` cover the review and the tool reply.
- `test_reputation_record_needs_a_known_outcome` and `test_a_threat_intel_entry_with_no_outcome_is_a_miss` cover the model and the cached record.
