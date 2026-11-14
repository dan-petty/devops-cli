## ADDED Requirements

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
