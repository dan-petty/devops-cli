## ADDED Requirements

### Requirement: A run records and counts the model that answered
`record_run_spend` SHALL store the model name of the replies of a run in `served_model` of the spend record, and SHALL add 1 for each reply to `devops_cli_ai_model_answers_total` with the labels `asked`, `answered` and `fallback`. `fallback` SHALL be `true` when the answered model is neither the asked model nor the asked model under a provider prefix, and `false` otherwise. A reply with no model name SHALL add no count.

#### Scenario: Another model answers
- **WHEN** a run of `claude-sonnet-5-5` ends with a reply that names `deepseek-v4.1-flash-1017`
- **THEN** the record has `model` `claude-sonnet-5-5` and `served_model` `deepseek-v4.1-flash-1017`, and the count has `fallback` `true`

#### Scenario: The asked model answers under a provider prefix
- **WHEN** a run of `qwen3-coder:30b` ends with a reply that names `ollama_chat/qwen3-coder:30b`
- **THEN** the count has `fallback` `false`

#### Scenario: A reply names no model
- **WHEN** a run ends with a reply that has no model name
- **THEN** the run adds no answer count
