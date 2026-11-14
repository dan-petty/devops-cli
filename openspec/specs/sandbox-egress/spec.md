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

### Requirement: The public whitelist validator accepts a public IP literal
The public whitelist validator SHALL accept an IPv4 or IPv6 address or CIDR whose network is public. It SHALL refuse a literal whose network is loopback, private, link-local or cloud metadata, with the same message it gives a name, and SHALL make no DNS lookup for a name.

#### Scenario: A public IPv6 CIDR is accepted
- **WHEN** `public_whitelist` holds `2606:4700::/48`, `2606:4700::1/48` or `2606:4700::1111`
- **THEN** `SandboxNetworkConfig` is valid and its policy holds one `ipBlock` on TCP 443 with the network `2606:4700::/48`, `2606:4700::/48` or `2606:4700::1111/128`

#### Scenario: A non-public IPv6 literal is refused
- **WHEN** `public_whitelist` holds `fd00::/8`, `::1/128`, `fe80::/10` or `fd00:ec2::254`
- **THEN** `SandboxNetworkConfig` raises a validation error that names the entry and says it cannot be private, loopback, or metadata

#### Scenario: A public IPv4 CIDR keeps its rule
- **WHEN** `public_whitelist` holds `140.82.112.0/20`
- **THEN** `SandboxNetworkConfig` is valid and its policy holds one `ipBlock` with that CIDR on TCP 443

#### Scenario: A name makes no lookup
- **WHEN** `public_whitelist` holds `localhost` and the DNS fake records each lookup
- **THEN** the config raises a validation error and the DNS fake records no lookup

### Requirement: The command prints a public IPv6 CIDR
`devops sandbox network-policy --network-mode public_whitelist --public-whitelist <cidr>` SHALL print the policy of a public IPv6 CIDR and exit 0.

#### Scenario: The command with an IPv6 CIDR
- **WHEN** the user runs the command with `2606:4700::/48`
- **THEN** it exits 0 and its YAML holds an egress rule with `ipBlock` `2606:4700::/48` on TCP 443
