# sandbox-egress Specification

## Purpose
The workload sandbox resolves each host name one time. The Prometheus metrics scrape resolves its host at the connect. The whitelist NetworkPolicy builder resolves each name with the resolve-and-check function of the egress policy.

## Requirements

### Requirement: The sandbox metrics scrape dials at the loopback level
The Prometheus scrape of the workload sandbox SHALL dial loopback and public addresses. It SHALL NOT dial a private address, whatever `ai.allow_private_network` says.

#### Scenario: A scrape host that answers loopback and then a private address
- **WHEN** the scrape host answers `127.0.0.1` and then a private address, with or without `ai.allow_private_network`
- **THEN** the scrape dials `127.0.0.1` and refuses the private address with no dial

### Requirement: The sandbox metrics scrape resolves its host one time
The Prometheus scrape SHALL resolve its host one time for each scrape, at the connect, and SHALL give the socket the address that it checked.

#### Scenario: A scrape of a named host
- **WHEN** the scrape reads `http://example.com:9100/metrics`, and `example.com` answers a public address
- **THEN** the scrape looks up `example.com` one time, and the socket gets the public address on port 9100

### Requirement: The whitelist NetworkPolicy resolves each name one time
The NetworkPolicy builder of the `public_whitelist` and `local_whitelist` modes SHALL resolve each whitelist host name one time, at the port of the entry. The whitelist validators SHALL NOT resolve a name.

#### Scenario: A public whitelist of two names
- **WHEN** the builder makes the policy for the public whitelist `example.com` and `example.org:8443`
- **THEN** the builder looks up each name one time

#### Scenario: A local whitelist name
- **WHEN** the builder makes the policy for the local whitelist `node1.example.internal`, which answers `192.0.2.10`
- **THEN** the builder looks up the name one time

### Requirement: The public whitelist admits only public answers
The NetworkPolicy builder SHALL refuse a public whitelist name that is a cloud metadata name, before any lookup. It SHALL refuse a public whitelist name that answers a cloud metadata address, a scoped IPv6 address or an address that is not public. The refusal SHALL be a `SandboxValidationError` that names the host, and also the answer if the builder refuses an answer. `devops sandbox network-policy` SHALL exit 1 and print no policy.

#### Scenario: A cloud metadata name
- **WHEN** the builder makes the policy for the public whitelist `metadata.google.internal`
- **THEN** the builder refuses the name with no lookup

#### Scenario: A non-public answer
- **WHEN** the public whitelist name `example.com` answers `169.254.169.254`, `127.0.0.1` or `192.0.2.10`
- **THEN** the builder refuses the name with a `SandboxValidationError` that names `example.com` and the answer

#### Scenario: The command with a refused name
- **WHEN** `devops sandbox network-policy --network-mode public_whitelist --public-whitelist example.com` runs, and `example.com` answers `192.0.2.10`
- **THEN** the command exits 1, names `example.com` and `192.0.2.10`, and prints no policy

### Requirement: The local whitelist admits only private or loopback answers
The NetworkPolicy builder SHALL refuse a local whitelist name that is a cloud metadata name, before any lookup. It SHALL refuse a local whitelist name that answers a cloud metadata address, a scoped IPv6 address, a link-local address or a public address. The refusal SHALL be a `SandboxValidationError` that names the host, and also the answer if the builder refuses an answer.

#### Scenario: A cloud metadata name
- **WHEN** the builder makes the policy for the local whitelist `metadata.google.internal`
- **THEN** the builder refuses the name with no lookup

#### Scenario: An answer outside the local whitelist
- **WHEN** the local whitelist name `node1.example.internal` answers `169.254.169.254`, `fe80::1%2` or a public address
- **THEN** the builder refuses the name with a `SandboxValidationError` that names `node1.example.internal` and the answer

### Requirement: A whitelist name with no answer is refused
The NetworkPolicy builder SHALL refuse a whitelist name whose lookup fails, with a `SandboxValidationError` that names the host.

#### Scenario: A name that does not resolve
- **WHEN** the lookup of the whitelist name `example.com` fails
- **THEN** the builder refuses the name with a `SandboxValidationError` that names `example.com`
