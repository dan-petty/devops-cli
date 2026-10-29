## Purpose

How a threat-intelligence record names the end of its lookup. It also states how the review and the `security_intel_network` tool show a lookup that did not succeed. A failed lookup never reads as a verified address.

## ADDED Requirements

### Requirement: A record names the outcome of its lookup
A `NetworkReputationRecord` SHALL name its outcome: `ok`, `unavailable` or `failed`. The outcome SHALL have no default. A record that names no outcome, or another value, SHALL be refused.

#### Scenario: A record with no outcome
- **WHEN** a `NetworkReputationRecord` is built with a target and no outcome
- **THEN** the model raises a validation error

#### Scenario: A cached record with no outcome
- **WHEN** the Valkey tier holds a record of a domain that has no outcome
- **THEN** the Radar client treats the entry as a miss and asks Radar

### Requirement: A Shodan InternetDB lookup that did not succeed is not an ok record
The Shodan InternetDB client SHALL give the outcome `failed` for a lookup that raises an error. It SHALL give `failed` for each reply with a status other than 200, 404 and 429. It SHALL give `unavailable` for a reply of 429 and for a target that is a domain. It SHALL give `ok` for a documented example or a local address, and it SHALL send no request about them.

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

#### Scenario: A domain
- **WHEN** the client looks up `service-domain.org`
- **THEN** the client sends no request and the record has the outcome `unavailable`

### Requirement: A Shodan InternetDB reply is ok only with the body of InternetDB
The Shodan InternetDB client SHALL give the outcome `ok` for a reply of 200 only when the body holds `ip`, `ports` and `vulns`. The `ports` SHALL be a list of integers, and the `vulns` SHALL be a list of text. The client SHALL give `ok` for a reply of 404 only when the `detail` of the body is "No information available". Any other body SHALL give the outcome `failed`.

#### Scenario: A reply of 200 with an empty body object
- **WHEN** the API answers 200 with the body `{}`
- **THEN** the record has the outcome `failed`

#### Scenario: A reply of 200 with the wrong type
- **WHEN** the API answers 200 with `ports` set to the text `80`
- **THEN** the record has the outcome `failed`

#### Scenario: A reply of 404 with a page
- **WHEN** the API answers 404 with an HTML page
- **THEN** the record has the outcome `failed`

#### Scenario: A reply of 404 for a missing route
- **WHEN** the API answers 404 with the body `{"detail": "Not Found"}`
- **THEN** the record has the outcome `failed`

#### Scenario: A reply of 404 with no data
- **WHEN** the API answers 404 with the body `{"detail": "No information available"}`
- **THEN** the record has the outcome `ok` and the summary "Clean / No open ports detected in InternetDB"

### Requirement: The Shodan InternetDB client keeps ok records only
The Shodan InternetDB client SHALL keep a record in memory only when its outcome is `ok`. A call for an address whose last lookup did not succeed SHALL send a new request.

#### Scenario: A call after a failed lookup
- **WHEN** a lookup of a public address fails and the client looks up the same address again
- **THEN** the second call sends a new request

#### Scenario: A call after an answered lookup
- **WHEN** the API answers 200 with the body of InternetDB and the client looks up the same address again
- **THEN** the second call sends no request and gives the same record

### Requirement: The review shows a lookup that did not succeed as unchecked
The review SHALL show a network reference as "Unchecked" when its record has the outcome `unavailable` or `failed`. It SHALL also show "Unchecked" when no lookup gave a record for the reference.

#### Scenario: A failed Shodan lookup
- **WHEN** a review with threat intelligence builds the payload of a file that names a public address, and the Shodan lookup fails
- **THEN** the security status of the network reference is "Unchecked"

#### Scenario: A reference that no lookup answered
- **WHEN** a dry run of a review with threat intelligence builds the payload of a file that names a public address
- **THEN** the security status of the reference is "Unchecked" and its record has the outcome `unavailable`

### Requirement: An unchecked reference ranks above a safe one
The report and the table of network references SHALL rank the status "Unchecked" after the flagged and the medium statuses and before every safe status. When two references of one target differ in status, the merged row SHALL keep the one that ranks first. The report and the table SHALL color an "Unchecked" status yellow.

#### Scenario: Two references of one target
- **WHEN** one target has a reference with the status "✓ Safe / Low Risk" and a reference with the status "Unchecked"
- **THEN** the merged row has the status "Unchecked", whichever reference comes first

#### Scenario: A mixed list of references
- **WHEN** the list holds a flagged, an unchecked, a "✓ Safe / Low Risk" and a "✓ Safe (Ports: 80)" reference
- **THEN** the report lists them in that order

#### Scenario: The color of an unchecked reference
- **WHEN** the report prints an external reference with the status "Unchecked" and one with the status "✓ Safe (Ports: 80)"
- **THEN** the first status is yellow and the second status is green

### Requirement: The tool reply names no result for a lookup that did not succeed
The `security_intel_network` reply for a target whose lookup has the outcome `unavailable` or `failed` SHALL give the reputation summary only. For an address, it SHALL NOT list ports or CVEs as "None detected". For a domain, it SHALL NOT give a line of threat categories.

#### Scenario: A failed lookup of a public address
- **WHEN** the lookup of a public address fails and the user calls `security_intel_network` for it
- **THEN** the reply holds "lookup failed" and holds neither "None detected" nor "Safe"

#### Scenario: A failed lookup of a domain
- **WHEN** the Radar lookup of a domain fails and the user calls `security_intel_network` for it
- **THEN** the reply has no line of threat categories and holds neither "verified" nor "Safe"
