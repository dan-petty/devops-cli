## ADDED Requirements

### Requirement: The caches of a process share one Valkey cache tier
The embeddings engine, the threat-intel client and the library symbol store of `devops ai ingest` SHALL use one Valkey cache tier for each process, with one client, one connection pool and one circuit breaker. While Valkey is down, the process SHALL make one connection attempt in each cooldown, not one for each cache.

#### Scenario: Two engines, a Radar client and the library store
- **WHEN** a process builds two embeddings engines, a Radar client and the library store of `devops ai ingest`
- **THEN** the four caches hold the same tier

#### Scenario: A Valkey that refuses each connection
- **WHEN** the configured Valkey refuses each connection, and each of the four caches reads a key
- **THEN** each read is a miss, and the process dials Valkey one time

### Requirement: The cache tier waits a short time for a connection
The shared cache tier SHALL wait at most `DEFAULT_VALKEY_CACHE_CONNECT_TIMEOUT_SECONDS` (0.25 s) for a connection, and never longer than `valkey.timeout`. A command SHALL wait `valkey.timeout`.

#### Scenario: The default timeout
- **WHEN** `valkey.timeout` is 2.0
- **THEN** a command of the tier waits 2.0 s and a connection waits 0.25 s

#### Scenario: A timeout shorter than the default connect wait
- **WHEN** `valkey.timeout` is 0.05
- **THEN** a command and a connection of the tier each wait 0.05 s

### Requirement: A cache tier that cannot be built leaves the caches without Valkey
When the shared tier cannot be built, the process SHALL log one warning that names the cause, and each cache SHALL run with no Valkey tier.

#### Scenario: A valkey.url that is not valid
- **WHEN** `valkey.url` is `valkey://example.com:99999`, and a process builds two engines, a Radar client and the library store
- **THEN** none of the four caches has a Valkey tier, and the process logs one warning that names `valkey.url`
