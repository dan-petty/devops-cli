## ADDED Requirements

### Requirement: The research agent may send requests to api.github.com and www.cisa.gov
The owner approved, on 2026-11-07, the egress of the research agent to `api.github.com` (the advisories API, for `GET /advisories` and `GET /repos/{owner}/{repo}/security-advisories`) and to `www.cisa.gov` (the Known Exploited Vulnerabilities list). The approval has the public egress level and a byte cap on each reply. `devops research advisories` SHALL send a request to these two hosts and to no other host that this approval names, and its clients SHALL send no contact data in any header.

#### Scenario: The hosts of a run
- **WHEN** `devops research advisories` runs on a repository with a GitHub Action, a mapped chart and a finding with a CVE, and no Python or Node package
- **THEN** the requests go to `api.github.com` and `www.cisa.gov` only

### Requirement: The GitHub advisories client and the KEV client refuse an answer they cannot trust
The GitHub advisories client SHALL read each reply as a stream, and SHALL treat a reply over `DEFAULT_GITHUB_ADVISORIES_MAX_RESPONSE_BYTES` as a failed read. The KEV client SHALL do the same for `DEFAULT_KEV_MAX_RESPONSE_BYTES`. Neither client SHALL follow a redirect: a redirect is a failed read, and the client SHALL send no request to its target, whatever the target is. A read that fails SHALL NOT be a clean package.

#### Scenario: A reply over the byte cap
- **WHEN** `api.github.com` or `www.cisa.gov` answers with a body of more than the cap of the client
- **THEN** the read is failed, with a reason that names the cap

#### Scenario: A redirect
- **WHEN** one of the two hosts answers with a redirect to another host, to a private address or to a cloud metadata address
- **THEN** the read is failed with the reason `GitHub returned status 302` or `CISA KEV returned status 302`, and no request goes to the target

### Requirement: The GitHub advisories client reads pages only on api.github.com
The GitHub advisories client SHALL read the next page of a list only when its URL is on `api.github.com`, and SHALL read at most `DEFAULT_GITHUB_ADVISORIES_MAX_PAGES` pages.

#### Scenario: A next page on another host
- **WHEN** the `Link` header of a list names a next page on a host other than `api.github.com`
- **THEN** the read is failed and no request goes to that host

#### Scenario: More pages than the client reads
- **WHEN** a list names a next page after `DEFAULT_GITHUB_ADVISORIES_MAX_PAGES` pages
- **THEN** the read is failed

### Requirement: The GitHub token goes to api.github.com only
The GitHub advisories client SHALL send an `Authorization` header when it holds a token, and only to `api.github.com`. The KEV client SHALL send no token. The command SHALL run with no token, at the lower rate limit of GitHub.

#### Scenario: A run with a token
- **WHEN** the command runs with a GitHub token
- **THEN** each request to `api.github.com` carries the token and no request to `www.cisa.gov` does

#### Scenario: A run with no token
- **WHEN** the process has no GitHub token
- **THEN** the command runs and no request carries an `Authorization` header

## MODIFIED Requirements

### Requirement: Public API clients dial only public addresses
The OSV client, the GitHub advisories client, the CISA KEV client, the Shodan InternetDB client, the Cloudflare Radar client and the Cloudflare API client SHALL dial only public addresses, whatever `ai.allow_private_network` says. A client SHALL NOT dial a loopback, private or link-local answer for its API host.

#### Scenario: A non-public answer without the flag
- **WHEN** `ai.allow_private_network` is false, and the API host (`api.osv.dev`, `api.github.com`, `www.cisa.gov`, `internetdb.shodan.io` or `api.cloudflare.com`) answers `127.0.0.1` and then a private address
- **THEN** the client dials neither address

#### Scenario: A non-public answer with the flag
- **WHEN** `ai.allow_private_network` is true, and the API host answers `127.0.0.1` and then a private address
- **THEN** the client dials neither address

### Requirement: The public API clients name themselves without contact data
The OSV client, the GitHub advisories client, the CISA KEV client, the Shodan InternetDB client and the Cloudflare Radar client SHALL send the User-Agent `devops-cli/<version>`. No e-mail address and no other contact data SHALL be in a header.

#### Scenario: The name of a client
- **WHEN** one of the five clients is built
- **THEN** its User-Agent is `devops-cli/<version>`
