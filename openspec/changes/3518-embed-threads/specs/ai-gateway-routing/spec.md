## MODIFIED Requirements

### Requirement: An embedding-only tier serves embedding models first
A tier at or below `embedding_only` SHALL keep one model loaded, SHALL set `LLAMA_ARG_THREADS` to 1, SHALL have the speed tier `embed` and a name with `embed`, and each of its gateway deployments SHALL have order 1. The render SHALL fail and name each group when a generation deployment names such a tier.

#### Scenario: An embedding-only tier
- **WHEN** a tier is rendered at or below `embedding_only`
- **THEN** `OLLAMA_MAX_LOADED_MODELS` is 1, and `LLAMA_ARG_THREADS` is 1, and `OLLAMA_CONTEXT_LENGTH` is the largest RAG chunk, and each embedding deployment has order 1

#### Scenario: A chat tier keeps its CPU threads
- **WHEN** only `per_gpu` includes a tier
- **THEN** the tier does not set `LLAMA_ARG_THREADS`

#### Scenario: A chat route on an embedding-only tier
- **WHEN** a generation deployment names an embedding-only tier
- **THEN** the render fails, names the group and writes no file
