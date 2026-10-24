# Spec Delta

## Purpose

The Valkey tier of the caches of devops-cli (the embeddings engine, the threat-intel client and the library symbol store): how a Valkey outage turns the tier off for a cooldown, and how a trial after the cooldown turns it on again.

## ADDED Requirements

### Requirement: A failed Valkey command turns the cache tier off for a cooldown
When a read or a write of the Valkey cache tier fails, the circuit breaker of the tier SHALL open. For `DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS` (60 s), the tier SHALL send no command to Valkey: a read SHALL be a miss, and a write SHALL NOT occur. The cache SHALL continue with its other tiers.

#### Scenario: Reads in the cooldown do not reach Valkey
- **WHEN** a read fails because Valkey is down, Valkey then holds the value of the key again, and the tier reads the key 100 times in the cooldown
- **THEN** each of the 100 reads is a miss, and a write in the cooldown is not in Valkey

#### Scenario: The embeddings engine in an outage
- **WHEN** an engine reads an embedding while Valkey is down, and in the cooldown embeds a text whose vector Valkey holds
- **THEN** the embedding provider receives both texts

#### Scenario: The threat-intel client in an outage
- **WHEN** the threat-intel client reads a record while Valkey is down, and in the cooldown looks up a domain whose record Valkey holds
- **THEN** Radar answers both lookups, and the record that Radar sent in the cooldown is not in Valkey

#### Scenario: The library symbol store in an outage
- **WHEN** the library symbol store reads a symbol while Valkey is down, and in the cooldown looks up a symbol whose signature Valkey holds
- **THEN** the local contracts answer both lookups

#### Scenario: A Valkey that refuses each connection
- **WHEN** the configured Valkey refuses each connection, and an engine embeds a text two times in the cooldown and one time after it
- **THEN** the engine embeds the three texts, and it dials Valkey one time in the cooldown and one time after it

### Requirement: A trial after the cooldown turns the cache tier on again
The first command of the tier after the cooldown SHALL be a trial, in the half-open state. A trial that succeeds SHALL close the breaker, and the tier SHALL send each later command to Valkey. A trial that fails SHALL open the breaker for one more cooldown. The tier SHALL record each change of the state of its breaker in the debug log.

#### Scenario: A trial that succeeds
- **WHEN** the cooldown has passed and Valkey is up
- **THEN** the next read gets the value from Valkey, a write after it is in Valkey, and the debug log records the changes from closed to open, from open to half-open and from half-open to closed

#### Scenario: A trial that fails
- **WHEN** the cooldown has passed and Valkey is still down
- **THEN** the trial read is a miss, a read 59 s later is a miss although Valkey is up again, a read 60 s after the trial gets the value, and the debug log records the change from half-open to open between the two changes from open to half-open

#### Scenario: Each cache comes back
- **WHEN** the cooldown after an outage has passed, Valkey is up, and it holds a vector, a threat-intel record and a symbol signature
- **THEN** the engine embeds the text with no request to the provider, the threat-intel client answers the lookup with no request to Radar, and the symbol store returns the signature from Valkey

### Requirement: A reply error does not turn the cache tier off
A reply error from a server that answers (`ValkeyCommandError`) SHALL make the read a miss, and SHALL NOT open the breaker.

#### Scenario: A read of a key that holds a list
- **WHEN** the tier reads a key that holds a list
- **THEN** the read is a miss, the next read of a string key gets its value from Valkey, and the debug log records no change of state

### Requirement: A corrupt cache entry is a miss
A threat-intel entry in Valkey that is not a valid record SHALL be a miss, and SHALL NOT turn the tier off.

#### Scenario: A corrupt threat-intel entry
- **WHEN** Valkey holds `not valid json {{` for a domain, and the threat-intel client looks up the domain
- **THEN** Radar answers the lookup, and its record replaces the corrupt entry in Valkey
