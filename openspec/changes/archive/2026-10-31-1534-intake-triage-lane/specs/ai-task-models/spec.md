# Spec Delta

## ADDED Requirements

### Requirement: Intake proposal uses triage task settings
When roadmap intake requests a candidate proposal, the LLM client SHALL use configuration from `ai.tasks.triage` if configured, or fall back to global `ai` settings when unset.

#### Scenario: Triage task model configured
- **WHEN** `ai.tasks.triage.model` is set
- **THEN** intake initializes its LLM client with the configured triage model

#### Scenario: Triage task model unset
- **WHEN** `ai.tasks.triage.model` is unset
- **THEN** intake initializes its LLM client with the global `ai.model` setting
