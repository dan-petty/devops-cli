## ADDED Requirements

### Requirement: The threat-intel memory tier has a bound and an expiry
The memory tier of the threat-intel client SHALL hold at most 1,000 records, and SHALL drop the least recently used record when it is full. A record SHALL expire after the client's threat-intel TTL (`valkey.threat_intel_ttl`, or the `ttl` the client is built with), and a lookup after that SHALL ask Radar again.

#### Scenario: A record expires after the TTL
- **WHEN** a client built with a TTL of 60 s looks up a domain, the clock moves 59 s, the client looks it up again, the clock moves 1 s more, and the client looks it up a third time
- **THEN** Radar is asked on the first and the third lookup, and not on the second

#### Scenario: A full memory tier drops the least recently used record
- **WHEN** a client looks up one domain through Radar, then looks up 1,000 other domains that Radar is never asked about, then looks up the first domain again
- **THEN** Radar is asked about the first domain two times
