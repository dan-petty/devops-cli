## Purpose

How a threat-intelligence record names the end of its lookup, and how the review and the `security_intel_network` tool show a lookup that did not succeed. A failed lookup never reads as a verified address.

## ADDED Requirements

### Requirement: A record names the outcome of its lookup
A `NetworkReputationRecord` SHALL name its outcome, one of `ok`, `unavailable` and `failed`. The outcome SHALL have no default, so a record that names none, or any other value, is refused.

#### Scenario: A record with no outcome
- **WHEN** a `NetworkReputationRecord` is built with a target and no outcome
- **THEN** the model raises a validation error

#### Scenario: A cached record with no outcome
- **WHEN** the Valkey tier holds a record of a domain that has no outcome
- **THEN** the Radar client treats the entry as a miss and asks Radar

### Requirement: A Shodan InternetDB lookup that did not succeed is not an ok record
The Shodan InternetDB client SHALL give the outcome `failed` for a lookup that raises an error and for each reply with a status other than 200, 404 and 429. It SHALL give `unavailable` for a reply of 429 and for a target that is a domain. It SHALL give `ok` for a reply of 200 or 404, and for a documented example or a local address, which it sends no request about.

#### Scenario: A private answer for the API host
- **WHEN** `internetdb.shodan.io` answers `10.0.0.1` and the client looks up a public address
- **THEN** the record has the outcome `failed` and a summary that starts with "Shodan InternetDB lookup failed"

#### Scenario: A failed connect
- **WHEN** the connect to the API host raises `OSError`
- **THEN** the record has the outcome `failed`

#### Scenario: A server error
- **WHEN** the API answers 500
- **THEN** the record has the outcome `failed`

#### Scenario: A rate limit
- **WHEN** the API answers 429
- **THEN** the record has the outcome `unavailable`

#### Scenario: A reply with no data
- **WHEN** the API answers 404
- **THEN** the record has the outcome `ok` and the summary "Clean / No open ports detected in InternetDB"

#### Scenario: A domain
- **WHEN** the client looks up `service-domain.org`
- **THEN** the client sends no request and the record has the outcome `unavailable`

### Requirement: The Shodan InternetDB client keeps ok records only
The Shodan InternetDB client SHALL keep a record in memory only when its outcome is `ok`. A call for an address whose last lookup did not succeed SHALL send a new request.

#### Scenario: A call after a failed lookup
- **WHEN** a lookup of a public address fails and the client looks up the same address again
- **THEN** the second call sends a new request

#### Scenario: A call after an answered lookup
- **WHEN** the API answers 200 for a public address and the client looks up the same address again
- **THEN** the second call sends no request and gives the same record

### Requirement: The review shows a lookup that did not succeed as unchecked
The review SHALL show a network reference as "Unchecked" when its record has the outcome `unavailable` or `failed`, and when no lookup gave a record for it. When a lookup client raises, the review SHALL give the reference a record with the outcome `failed` and the reason.

#### Scenario: A failed Shodan lookup
- **WHEN** the Shodan lookup of a public address in a file fails and the review builds the payload of the file
- **THEN** the security status of the network reference is "Unchecked"

#### Scenario: A reference that no lookup answered
- **WHEN** the review builds a payload for a network reference that has no record in the lookup results, as in a dry run
- **THEN** the security status of the reference is "Unchecked", and its record has the outcome `unavailable`

#### Scenario: A client that raises
- **WHEN** the address client or the domain client raises an error during the review
- **THEN** the fallback record of each target has the outcome `failed` and the text of the error in its summary

### Requirement: The tool reply names no result for a lookup that did not succeed
The `security_intel_network` reply for a public address whose lookup has the outcome `unavailable` or `failed` SHALL give the reputation summary only. It SHALL NOT list the ports or the CVEs as "None detected".

#### Scenario: A failed lookup of a public address
- **WHEN** the lookup of a public address fails and the user calls `security_intel_network` for it
- **THEN** the reply holds "lookup failed" and holds neither "None detected" nor "Safe"
