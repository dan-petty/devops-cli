## ADDED Requirements

### Requirement: The embedding task keeps its model when a source sets another of its fields
When a variable or a config file sets a field of `ai.tasks.embedding` other than `model`, the embedding task SHALL keep the embedding model `qwen3-embedding:0.6b` as its model.

#### Scenario: A variable sets the embedding timeout
- **WHEN** `DEVOPS_CLI_AI_TASK_EMBEDDING_TIMEOUT` is `45` and the settings load
- **THEN** `ai.tasks.embedding.model` is `qwen3-embedding:0.6b` and its timeout is `45.0`

#### Scenario: A config file sets the embedding timeout
- **WHEN** the project config file holds `ai.tasks.embedding.timeout: 45` and the settings load
- **THEN** `ai.tasks.embedding.model` is `qwen3-embedding:0.6b` and its timeout is `45.0`
