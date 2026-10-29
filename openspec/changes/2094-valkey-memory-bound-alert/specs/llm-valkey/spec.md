## ADDED Requirements

### Requirement: A Valkey that refuses writes at its bound alerts before it reaches it
The Prometheus server SHALL fire `ValkeyMemoryNearBound` with the severity `warning` for each Valkey whose exporter reports the policy `noeviction`, a `maxmemory` above 0, and used memory above 80% of `maxmemory` for 10 minutes. The alert SHALL keep the namespace, job and instance of the exporter.

#### Scenario: The cache Valkey at 90% of its bound
- **WHEN** the `valkey-memory` group is evaluated over a Valkey with the policy `noeviction`, a `maxmemory` of 1000 bytes and 900 bytes used
- **THEN** at 5 minutes no alert fires
- **AND** at 15 minutes `ValkeyMemoryNearBound` fires with its namespace, job and instance, and the summary names 90%

#### Scenario: A Valkey under the threshold, an evicting Valkey and a Valkey with no bound
- **WHEN** a `noeviction` Valkey uses 500 of 1000 bytes, an `allkeys-lru` Valkey uses 950 of 1000 bytes, and a `noeviction` Valkey has a `maxmemory` of 0
- **THEN** `ValkeyMemoryNearBound` does not fire at 15 minutes
