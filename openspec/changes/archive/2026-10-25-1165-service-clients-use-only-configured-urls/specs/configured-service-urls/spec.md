# Spec Delta

## Purpose

Ensures that every service client uses only configured URLs or connections that the CLI opened itself, and stops with an error naming the setting when no configuration exists.

## ADDED Requirements

### Requirement: AI callers use only configured endpoints

Every AI caller SHALL obtain its endpoint URL from the active configuration. If the configured provider has no endpoint configured, the caller SHALL stop with a configuration error that names the missing setting. An AI caller SHALL NOT fall back to an unconfigured localhost or loopback address.

#### Scenario: Ollama provider with no configured URLs
- **WHEN** `ai.provider` is `ollama` and `ai.ollama_urls` is empty
- **THEN** executing an AI command fails with an error naming `ai.ollama_urls`

#### Scenario: Gateway provider with no gateway URL
- **WHEN** `ai.provider` is `gateway` and `ai.gateway_url` is not set
- **THEN** executing an AI command fails with an error naming `ai.gateway_url`

### Requirement: Service clients refuse unconfigured endpoints

Service clients for Qdrant, Tempo, Pyroscope, and Vault SHALL connect only to configured endpoints or ports opened by CLI port forwards. When a required endpoint setting is not configured, the command SHALL exit non-zero with an error naming the missing configuration key.

#### Scenario: Qdrant client without configured URL
- **WHEN** `qdrant.url` is not set and `devops rag query "test"` runs
- **THEN** the command exits non-zero with an error naming `qdrant.url`

#### Scenario: Observability without configured Tempo URL
- **WHEN** `tempo.url` is not set and `devops telemetry waterfall <trace-id>` runs
- **THEN** the command exits non-zero with an error naming `tempo.url`

### Requirement: Embedding benchmark defaults to configured embedding model

The embedding benchmark command SHALL default to the configured embedding model for the active provider. When all requests in a benchmark run fail, the command SHALL exit non-zero and SHALL NOT save the benchmark run record.

#### Scenario: Embedding benchmark model selection
- **WHEN** `devops ai benchmark --type embedding` runs without `--models`
- **THEN** candidate models default to the configured embedding model or gateway alias `devops-embedding`

#### Scenario: Embedding benchmark failed run
- **WHEN** every request in an embedding benchmark fails
- **THEN** the command exits with exit code 1 and records no run in the benchmark store
