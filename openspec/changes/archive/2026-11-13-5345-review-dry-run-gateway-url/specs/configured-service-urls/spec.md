## ADDED Requirements

### Requirement: A review dry run takes its model endpoint from the configuration
The dry-run plan of a review command SHALL get the target of each model request from the configured AI endpoint, by the resolver that the review run uses. The model request of a review SHALL use the `analysis` task settings. When the resolver names a setting that is not set, the plan target SHALL start with that setting as a placeholder, such as `<ai.gateway_url>`, and the dry run SHALL make zero requests. A plan target SHALL NOT hold a gateway, Ollama or loopback address that no setting gives.

#### Scenario: Gateway provider with no gateway URL
- **WHEN** `ai.provider` is `gateway`, `ai.gateway_url` is not set and `devops review path src --dry-run` runs
- **THEN** the command exits 0 and its plan has the request `POST <ai.gateway_url>/chat/completions`

#### Scenario: Gateway provider with a gateway URL
- **WHEN** `ai.provider` is `gateway` and `ai.gateway_url` is `https://gateway.example.com/v1`
- **THEN** the review path plan has the request `POST https://gateway.example.com/v1/chat/completions`

#### Scenario: Ollama provider with no Ollama URLs
- **WHEN** `ai.provider` is `ollama` and `ai.ollama_urls` is empty
- **THEN** the review path plan has the request `POST <ai.ollama_urls>/api/chat`, and the corpus generate plan has the request `POST <ai.ollama_urls>/api/embeddings`

#### Scenario: The analysis task names its own provider
- **WHEN** `ai.provider` is `ollama` and `ai.tasks.analysis` sets the provider `gateway` with the base URL `https://gateway.example.com/v1`
- **THEN** the review path plan has the request `POST https://gateway.example.com/v1/chat/completions`
