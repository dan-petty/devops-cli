# public-api-egress Specification

## Purpose
Ensures that the clients of fixed public APIs (OSV, Shodan InternetDB, Cloudflare Radar and the Cloudflare API) dial only public addresses, and check each address at the connect.

## Requirements

### Requirement: Public API clients dial only public addresses
The OSV client, the Shodan InternetDB client, the Cloudflare Radar client and the Cloudflare API client SHALL dial only public addresses, whatever `ai.allow_private_network` says. A client SHALL NOT dial a loopback, private or link-local answer for its API host.

#### Scenario: A non-public answer without the flag
- **WHEN** `ai.allow_private_network` is false, and the API host (`api.osv.dev`, `internetdb.shodan.io` or `api.cloudflare.com`) answers `127.0.0.1` and then a private address
- **THEN** the client dials neither address

#### Scenario: A non-public answer with the flag
- **WHEN** `ai.allow_private_network` is true, and the API host answers `127.0.0.1` and then a private address
- **THEN** the client dials neither address

### Requirement: Public API clients dial the address that they checked
Each client of the requirement "Public API clients dial only public addresses" SHALL resolve its API host one time, at the connect, and SHALL give the socket the address that it checked, never the host name.

#### Scenario: A request to the API host
- **WHEN** one of these clients sends a request to its API host
- **THEN** the socket gets no host name

### Requirement: The cloudflare commands report a refused address
Each `devops cloudflare` command SHALL report a refused address of the Cloudflare API host with the message of `SSRFBlockedError`, and SHALL exit with its exit code, 2, with no traceback.

#### Scenario: A private answer for the Cloudflare API host
- **WHEN** `api.cloudflare.com` answers a private address, and the user runs a command of the `cloudflare`, `dns`, `tunnel` or `access` group
- **THEN** the command prints the refusal, exits with code 2 and sends no request to the address
