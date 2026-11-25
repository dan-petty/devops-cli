## MODIFIED Requirements

### Requirement: Embedding benchmark defaults to configured embedding model

The embedding benchmark command SHALL default to the configured embedding model (`qwen3-embedding:0.6b` when using the `gateway` provider). When all requests in a benchmark run fail, the command SHALL exit non-zero and SHALL NOT save the benchmark run record. When the provider is `gateway`, `plan_ai_benchmark` for `embedding` SHALL plan `POST /v1/embeddings` on the configured gateway URL rather than Ollama `/api/embeddings`.

#### Scenario: Embedding benchmark model selection
- **WHEN** `devops ai benchmark --type embedding` runs without `--models`
- **THEN** candidate models default to the configured embedding model or gateway model `qwen3-embedding:0.6b`

#### Scenario: Embedding benchmark gateway dry run
- **WHEN** `devops ai benchmark --type embedding --dry-run` runs with `provider` set to `gateway`
- **THEN** the planned request targets `<gateway>/v1/embeddings` with `qwen3-embedding:0.6b` and does not plan `/api/embeddings`

#### Scenario: Embedding benchmark failed run
- **WHEN** every request in an embedding benchmark fails
- **THEN** the command exits with exit code 1 and records no run in the benchmark store
