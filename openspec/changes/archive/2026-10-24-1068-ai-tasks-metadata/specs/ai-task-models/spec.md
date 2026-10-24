# ai-task-models Specification

## Purpose
Specifies AI model selection and configuration for specialized tasks including metadata generation and agent instruction synthesis.

## ADDED Requirements

### Requirement: Commands generating metadata or instruction files use metadata task settings
When `devops analyze path`, `branch`, or `pr` runs with `--enhanced`, and when `devops ai agents` runs, the LLM client SHALL use configuration from `ai.tasks.metadata` if configured, or fall back to global `ai` settings when unset.

#### Scenario: Metadata task model configured
- **WHEN** `ai.tasks.metadata.model` or `DEVOPS_CLI_AI_TASK_METADATA_MODEL` is set
- **THEN** `devops analyze` with `--enhanced` and `devops ai agents` initialize their LLM client with the configured metadata model

#### Scenario: Metadata task model unset
- **WHEN** `ai.tasks.metadata.model` is unset
- **THEN** `devops analyze` with `--enhanced` and `devops ai agents` initialize their LLM client with the global `ai.model` setting
