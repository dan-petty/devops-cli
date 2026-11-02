## ADDED Requirements

### Requirement: Non-public address classification uses maintained sources
The egress validation SHALL classify non-public addresses with Python's `ipaddress` properties and SHALL keep only rules that the standard library does not cover, each with an RFC comment and a test.

#### Scenario: IPv4 special-purpose address
- **WHEN** the classifier receives an address from the IANA IPv4 special-purpose registry
- **THEN** it returns the same non-public answer as `ipaddress.IPv4Address.is_global`.

#### Scenario: IPv6 special-purpose address
- **WHEN** the classifier receives an address from the IANA IPv6 special-purpose registry
- **THEN** it returns the same non-public answer as `ipaddress.IPv6Address.is_global`.

#### Scenario: Transition form of a non-public address
- **WHEN** the classifier receives a NAT64, Teredo, IPv4-mapped, ISATAP or IPv4-compatible form of a non-public address
- **THEN** it returns non-public.

#### Scenario: No private module copy
- **WHEN** a search of `src/` for `_ssrf` runs
- **THEN** it finds no match.

#### Scenario: Existing SSRF tests
- **WHEN** the existing SSRF tests run
- **THEN** they pass unchanged.
