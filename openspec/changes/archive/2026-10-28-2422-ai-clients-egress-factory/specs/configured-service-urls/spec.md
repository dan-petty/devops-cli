## ADDED Requirements

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
