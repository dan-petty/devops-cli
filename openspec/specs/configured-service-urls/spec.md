# configured-service-urls Specification

## Purpose
Ensures that every service client uses only configured URLs or connections that the CLI opened itself, and stops with an error naming the setting when no configuration exists.

## Requirements

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

### Requirement: Configured AI service clients dial at the configured level
The LLM gateway model query, the gateway health probe, the backend probe, the `devops ai gateway load` Prometheus query, the embeddings engine, the pydantic-ai Ollama model, the pydantic-ai provider base URL, the benchmark endpoints and the `--source` URL of `devops ai cost update-pricing` SHALL dial loopback and public addresses. They SHALL dial private addresses only when `ai.allow_private_network` is true.

#### Scenario: A configured client without the flag
- **WHEN** `ai.allow_private_network` is false, and the host of the gateway, Ollama, embeddings, Prometheus, benchmark or pricing source URL answers `127.0.0.1` and then `192.0.2.10`
- **THEN** the client dials `127.0.0.1` and refuses `192.0.2.10` with no dial

#### Scenario: A configured client with the flag
- **WHEN** `ai.allow_private_network` is true, and the host of one of these URLs answers `127.0.0.1` and then `192.0.2.10`
- **THEN** the client dials both addresses

#### Scenario: The pydantic-ai Ollama model on a private host
- **WHEN** `ai.allow_private_network` is false, and the host of `ai.ollama_urls` answers `192.0.2.10`
- **THEN** a request of the Ollama model of pydantic-ai is refused with no dial

### Requirement: The gateway connect probe dials private addresses
The probe of `devops ai gateway connect` SHALL dial loopback, public and private addresses, whatever `ai.allow_private_network` says.

#### Scenario: A gateway node on a private address
- **WHEN** the host of the gateway node answers `192.0.2.10`, and `ai.allow_private_network` is false
- **THEN** the probe dials `192.0.2.10`

### Requirement: The pricing registry and the documentation crawler dial only public addresses
The fetch of the default pricing registry and the documentation crawler SHALL dial only public addresses, whatever `ai.allow_private_network` says.

#### Scenario: A non-public answer
- **WHEN** the host of the crawled page or of the default pricing registry answers `127.0.0.1` or `192.0.2.10`, with or without `ai.allow_private_network`
- **THEN** the client refuses the address with no dial

### Requirement: AI service clients dial the address that they checked
Each AI service client of these requirements SHALL resolve the host one time, at the connect, and SHALL give the socket the address that it checked, never the host name. Each one SHALL refuse cloud metadata addresses.

#### Scenario: A host that answers differently at a later lookup
- **WHEN** the host of one of these URLs answers a public address at the first two lookups and `169.254.169.254` at each later lookup
- **THEN** the socket gets neither the host name nor `169.254.169.254`
