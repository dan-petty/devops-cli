# ai-task-models Specification

## Purpose
Specifies AI model selection and configuration for specialized tasks including metadata generation and agent instruction synthesis.

## Requirements

### Requirement: Commands generating metadata or instruction files use metadata task settings
When `devops analyze path`, `branch`, or `pr` runs with `--enhanced`, and when `devops ai agents` runs, the LLM client SHALL use configuration from `ai.tasks.metadata` if configured, or fall back to global `ai` settings when unset.

#### Scenario: Metadata task model configured
- **WHEN** `ai.tasks.metadata.model` or `DEVOPS_CLI_AI_TASK_METADATA_MODEL` is set
- **THEN** `devops analyze` with `--enhanced` and `devops ai agents` initialize their LLM client with the configured metadata model

#### Scenario: Metadata task model unset
- **WHEN** `ai.tasks.metadata.model` is unset
- **THEN** `devops analyze` with `--enhanced` and `devops ai agents` initialize their LLM client with the global `ai.model` setting

### Requirement: The embedding task keeps its model when a source sets another of its fields
When a variable or a config file sets a field of `ai.tasks.embedding` other than `model`, the embedding task SHALL keep the embedding model `qwen3-embedding:0.6b` as its model.

#### Scenario: A variable sets the embedding timeout
- **WHEN** `DEVOPS_CLI_AI_TASK_EMBEDDING_TIMEOUT` is `45` and the settings load
- **THEN** `ai.tasks.embedding.model` is `qwen3-embedding:0.6b` and its timeout is `45.0`

#### Scenario: A config file sets the embedding timeout
- **WHEN** the project config file holds `ai.tasks.embedding.timeout: 45` and the settings load
- **THEN** `ai.tasks.embedding.model` is `qwen3-embedding:0.6b` and its timeout is `45.0`
