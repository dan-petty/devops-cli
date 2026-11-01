## ADDED Requirements

### Requirement: Embedder raises EmbeddingsError for empty Ollama URL list
When ai.provider is ollama and no Ollama URL is configured, the embedder SHALL raise EmbeddingsError with the embedding_no_provider message and no traceback.

#### Scenario: Empty URL list with ollama provider
- **WHEN** ai.provider is ollama and ai.ollama_urls is empty and embed_texts is called with one text
- **THEN** EmbeddingsError is raised with the embedding_no_provider message and no ZeroDivisionError traceback appears
