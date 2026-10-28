# Spec Delta

## Purpose

Ensures that the clients of fixed public APIs (OSV, Shodan InternetDB, Cloudflare Radar and the Cloudflare API) dial only public addresses, and check each address at the connect.

## ADDED Requirements

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
