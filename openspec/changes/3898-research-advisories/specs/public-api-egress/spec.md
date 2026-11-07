## ADDED Requirements

### Requirement: The OSV client refuses an answer it cannot trust to be complete
The OSV client SHALL read each answer as a stream, and SHALL treat an answer over `DEFAULT_OSV_MAX_RESPONSE_BYTES` as a failed lookup. It SHALL follow no redirect: a redirect is a failed lookup, and the client SHALL send no request to its target, whatever the target is. A batch answer that names a next page SHALL be a failed lookup for its query.

#### Scenario: An answer over the byte cap
- **WHEN** `api.osv.dev` answers a batch query, a query or a record read with a body of more than `DEFAULT_OSV_MAX_RESPONSE_BYTES` bytes
- **THEN** the lookup is failed, with a reason that names the cap

#### Scenario: A redirect
- **WHEN** `api.osv.dev` answers the batch query with a redirect to another host, to a private address or to a cloud metadata address
- **THEN** the lookup is failed with the reason `OSV returned status 302`, and no request goes to the target

#### Scenario: A batch answer with a next page
- **WHEN** a result of the batch answer holds a `next_page_token`
- **THEN** the lookup of that query is failed

### Requirement: The OSV client sends batches the API takes
The OSV client SHALL send at most `DEFAULT_OSV_BATCH_MAX_QUERIES` queries in one batch request. A chunk whose request fails SHALL fail its own queries only.

#### Scenario: More queries than one batch takes
- **WHEN** the client is asked about 1001 packages
- **THEN** it sends two batch requests, with 1000 and 1 queries

### Requirement: The OSV client reads one record
The OSV client SHALL read one record with `GET /v1/vulns/{id}` and SHALL give the severity, the affected ranges and the fixed versions that the record names for the asked package. It SHALL read the ranges of the types `ECOSYSTEM` and `SEMVER` only.

#### Scenario: A record with a commit range
- **WHEN** a record holds a `GIT` range with a commit hash and an `ECOSYSTEM` range with the fix `5.4` for the package
- **THEN** the record the client returns has the fixed version `5.4` and no commit hash

### Requirement: The public API clients name themselves without contact data
The OSV client, the Shodan InternetDB client and the Cloudflare Radar client SHALL send the User-Agent `devops-cli/<version>`. No e-mail address and no other contact data SHALL be in a header.

#### Scenario: The name of a client
- **WHEN** one of the three clients is built
- **THEN** its User-Agent is `devops-cli/<version>`
