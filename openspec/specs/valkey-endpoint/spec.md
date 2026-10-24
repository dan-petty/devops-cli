# valkey-endpoint Specification

## Purpose
The endpoint that the Valkey clients of devops-cli dial from the `valkey` settings: the address that the settings name, and when the connection uses TLS with a certificate check against the host name.

## Requirements

### Requirement: The scheme of valkey.url decides TLS
When `valkey.url` has the scheme `valkeys` or `rediss`, each Valkey client that reads the `valkey` settings SHALL connect over TLS, send the host of the URL as the server name, and check the certificate against that host with the platform CA store. When `valkey.url` has the scheme `valkey`, the client SHALL connect in plaintext.

#### Scenario: A valkeys or rediss URL connects over TLS
- **WHEN** `valkey.url` is `valkeys://example.com:<port>` or `rediss://example.com:<port>`, and the server shows a certificate for `example.com` from a trusted CA
- **THEN** `devops valkey ping` connects over TLS, the server receives `PING`, and the command exits 0

#### Scenario: A certificate for another name is refused
- **WHEN** `valkey.url` is `valkeys://example.com:<port>`, and the server shows a certificate for `example.org` from a trusted CA
- **THEN** `devops valkey ping` exits 1, its output contains `certificate is not valid for 'example.com'`, and the server receives no command

#### Scenario: A valkey URL connects in plaintext
- **WHEN** `valkey.url` is `valkey://example.com:<port>`, and the server does not use TLS
- **THEN** `devops valkey ping` connects in plaintext, the server receives `PING`, and the command exits 0

#### Scenario: The dashboard panel connects over TLS
- **WHEN** `valkey.url` is `valkeys://example.com:<port>`, and the server shows a certificate for `example.com` from a trusted CA
- **THEN** the Valkey panel of the dashboard shows the server as connected, with the version, the uptime and the key count that the server sends

### Requirement: valkey.url names the address
When `valkey.url` has a Valkey scheme, the host and the port of the URL SHALL be the address that a Valkey client dials, also when the same configuration file holds `valkey.host` and `valkey.port`. The password of the URL SHALL NOT be part of the endpoint. When `valkey.url` has no Valkey scheme, the client SHALL dial `valkey.host` in plaintext. An environment override of `valkey.host` SHALL replace the host, behind the scheme of `valkey.url` unless the override names a Valkey scheme of its own.

#### Scenario: A saved file holds the default host and port
- **WHEN** the configuration file holds `valkey.host: localhost:6379`, `valkey.port: 6379` and `valkey.url: valkeys://example.com:6380`
- **THEN** the endpoint is `valkeys://example.com:6380`

#### Scenario: The password of the URL stays out of the endpoint
- **WHEN** `valkey.url` is `valkeys://:<masked-password>@example.com:6380`
- **THEN** the endpoint is `valkeys://example.com:6380`

#### Scenario: A URL with no Valkey scheme
- **WHEN** the configuration file holds `valkey.host: 192.0.2.7:30637` and `valkey.url: http://192.0.2.7:30637`
- **THEN** the endpoint is `192.0.2.7:30637`

#### Scenario: An environment override of the host
- **WHEN** `valkey.url` is `valkeys://example.com:6380` and `DEVOPS_CLI_VALKEY_HOST` is `example.org:6381`
- **THEN** the endpoint is `valkeys://example.org:6381`

#### Scenario: An environment override with its own scheme
- **WHEN** `valkey.url` is `valkey://example.com:6379` and `DEVOPS_CLI_VALKEY_HOST` is `valkeys://example.org:6381`
- **THEN** the endpoint is `valkeys://example.org:6381`
