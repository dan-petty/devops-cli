## ADDED Requirements

### Requirement: numeric-host-parsing
The egress checks SHALL parse a numeric IP host using socket.getaddrinfo with the AI_NUMERICHOST flag and classify the result with ipaddress.

#### Scenario: octal form is refused
- **WHEN** validate_url is called with http://0177.0.0.1/ and allow_private is False
- **THEN** the call raises an error refusing the private address

#### Scenario: three-part form is refused
- **WHEN** validate_url is called with http://127.0.1/ and allow_private is False
- **THEN** the call raises an error refusing the private address

#### Scenario: hex form is refused
- **WHEN** validate_url is called with http://0x7f.1/ and allow_private is False
- **THEN** the call raises an error refusing the private address

#### Scenario: integer form is refused
- **WHEN** validate_url is called with http://2130706433/ and allow_private is False
- **THEN** the call raises an error refusing the private address

### Requirement: unparsable-host-is-private
The egress checks SHALL treat a host value that does not parse as an IP address as private.

#### Scenario: unparsable value is treated as private
- **WHEN** is_private_ip is called with a value that does not parse as an IP address
- **THEN** the call returns True

### Requirement: ipv6-zone-id-stripped
The egress checks SHALL strip an IPv6 zone ID before classifying the address.

#### Scenario: link-local address with zone ID is refused
- **WHEN** is_loopback_or_private_host is called with fe80::1%eth0
- **THEN** the call returns True, treating the address as link-local
