## ADDED Requirements

### Requirement: per-call-sampling-in-request-payload
When a caller passes temperature, top_p, or seed to chat or chat_messages, the HTTP request body SHALL carry those values.

#### Scenario: caller-passes-temperature-and-seed
- **WHEN** A caller invokes client.chat(system, user, temperature=0.9, seed=7) against a fake model at the HTTP edge
- **THEN** The request body contains temperature 0.9 and seed 7

#### Scenario: caller-passes-top-p
- **WHEN** A caller invokes client.chat(system, user, top_p=0.8) against a fake model at the HTTP edge
- **THEN** The request body contains top_p 0.8

### Requirement: per-call-sampling-in-cache-key
The cache key generated for a chat call SHALL include the per-call temperature, top_p, and seed values when they are provided.

#### Scenario: two-calls-differ-only-in-temperature
- **WHEN** A caller invokes chat with temperature=0.1 and then with temperature=0.9 for the same system and user text
- **THEN** The two calls produce different cache keys

#### Scenario: two-calls-differ-only-in-seed
- **WHEN** A caller invokes chat with seed=7 and then with seed=42 for the same system and user text
- **THEN** The two calls produce different cache keys

### Requirement: config-default-fallback
When a caller does not pass a sampling parameter, the request SHALL use the value from the client's config.

#### Scenario: caller-omits-temperature
- **WHEN** A caller invokes client.chat(system, user) with config temperature set to 0.1
- **THEN** The request body contains temperature 0.1

#### Scenario: caller-omits-top-p
- **WHEN** A caller invokes client.chat(system, user) with config top_p set to 0.95
- **THEN** The request body contains top_p 0.95

### Requirement: unknown-keyword-argument-rejected
A call to chat or chat_messages with a keyword argument that is not a recognized parameter SHALL raise TypeError.

#### Scenario: caller-passes-unrecognized-keyword
- **WHEN** A caller invokes client.chat(system, user, unknown_param=1)
- **THEN** A TypeError is raised

### Requirement: seed-omitted-for-unsupported-providers
When the provider does not support seed, the request body SHALL omit the seed field even if the caller passes one.

#### Scenario: caller-passes-seed-to-claude-provider
- **WHEN** A caller invokes client.chat(system, user, seed=7) with provider set to claude
- **THEN** The request body does not contain a seed field
