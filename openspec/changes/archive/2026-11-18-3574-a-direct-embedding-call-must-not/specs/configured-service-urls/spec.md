## ADDED Requirements

### Requirement: Embedding URL setting
The AI configuration SHALL hold the setting `ai.embedding_ollama_urls`, whose default is the one-element list of `DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL`.

#### Scenario: No embedding URL is set
- **WHEN** no source sets `ai.embedding_ollama_urls`
- **THEN** the resolved embedding URL list is `[DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL]`.

#### Scenario: An operator sets one embedding URL
- **WHEN** `ai.embedding_ollama_urls` holds one URL
- **THEN** the resolved embedding URL list is that URL alone.

#### Scenario: An entry is no URL
- **WHEN** `ai.embedding_ollama_urls` holds an entry with no http or https scheme and host
- **THEN** the resolution raises a `ConfigurationError` that names the key `ai.embedding_ollama_urls`.

### Requirement: Embedding request reaches the embedding Service
The embedding engine MUST send a direct Ollama embedding request to a URL of `ai.embedding_ollama_urls` and MUST NOT send it to `ai.ollama_urls`.

#### Scenario: The chat URLs hold the default Service
- **WHEN** `ai.ollama_urls` holds `DEFAULT_OLLAMA_CLUSTER_URL` and `ai.provider` is `ollama`
- **THEN** the request goes to `DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL` and no request goes to `DEFAULT_OLLAMA_CLUSTER_URL`.

#### Scenario: The embedding setting is empty
- **WHEN** `ai.embedding_ollama_urls` is empty and `ai.ollama_urls` holds `DEFAULT_OLLAMA_CLUSTER_URL`
- **THEN** the engine raises `EmbeddingsError` and sends no request.

### Requirement: Configure URLs writes the embedding Service
`devops k8s configure-urls` SHALL write `DEFAULT_OLLAMA_EMBEDDING_CLUSTER_URL` into `ai.embedding_ollama_urls` when it detects a reachable address for the embedding Service, and SHALL keep the default Ollama Service only in `ai.ollama_urls`.

#### Scenario: Configure URLs against a cluster
- **WHEN** a person runs `devops k8s configure-urls --stack llm` for a cluster that answers for both Services
- **THEN** the written configuration holds the embedding Service as `ai.embedding_ollama_urls` and the default Ollama Service as `ai.ollama_urls`.

#### Scenario: The embedding Service answers nothing
- **WHEN** the cluster gives no reachable address for the embedding Service
- **THEN** the written configuration holds the default of `ai.embedding_ollama_urls` and the command reports the other configured keys.
