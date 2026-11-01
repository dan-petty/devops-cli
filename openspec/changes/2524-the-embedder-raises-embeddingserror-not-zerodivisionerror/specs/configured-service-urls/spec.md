## ADDED Requirements

### Requirement: The embeddings engine stops on a missing Ollama URL
When `ai.provider` is `ollama` and no Ollama URL is configured (`ai.ollama_urls` is empty and `ai.api_base_url` is not set), the embeddings engine SHALL raise an `EmbeddingsError` that names `ai.ollama_urls`. It SHALL NOT raise a `ZeroDivisionError`.

#### Scenario: The Ollama provider with an empty URL list
- **WHEN** `ai.provider` is `ollama`, `ai.ollama_urls` is empty, `ai.api_base_url` is not set, and `embed_texts` gets one text
- **THEN** it raises an `EmbeddingsError` whose message names `ai.ollama_urls`, and it stores no vector in the cache
