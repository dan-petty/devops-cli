## MODIFIED Requirements

### Requirement: A run records and counts the model that answered
`record_run_spend` SHALL store the model name of the replies of a run in `served_model` of the spend record, and SHALL add 1 for each reply to `devops_cli_ai_model_answers_total` with the labels `asked`, `answered`, `fallback` and `row`. The spend hook of `build_agent` SHALL add 1 with the same labels for the reply of each model request, and SHALL give the spend record the cached prompt tokens of the reply. `fallback` SHALL be `true` when the answered model is neither the asked model nor the asked model under a provider prefix, and `false` otherwise. A reply with no model name SHALL add no count. A request SHALL add one count only.

#### Scenario: Another model answers
- **WHEN** a run of `claude-sonnet-5-5` ends with a reply that names `deepseek-v4.1-flash-1017`
- **THEN** the record has `model` `claude-sonnet-5-5` and `served_model` `deepseek-v4.1-flash-1017`, and the count has `fallback` `true`

#### Scenario: The asked model answers under a provider prefix
- **WHEN** a run of `qwen3-coder:30b` ends with a reply that names `ollama_chat/qwen3-coder:30b`
- **THEN** the count has `fallback` `false`

#### Scenario: A reply names no model
- **WHEN** a run ends with a reply that has no model name
- **THEN** the run adds no answer count

#### Scenario: A stage, refine or alternatives run with two model requests
- **WHEN** the run of `investigate` sends two model requests in the row `refine`
- **THEN** the ledger has two records, and the answer count adds 2 with `row` `refine`

#### Scenario: A request with cached prompt tokens through the hook
- **WHEN** a request of an agent on the DeepSeek group reads 900,000 of its 1,000,000 prompt tokens from the cache of the provider
- **THEN** the record costs the cached input rate for the 900,000 tokens

## ADDED Requirements

### Requirement: The AI series name the job row that sent the request
`track_request_spend` SHALL add the label `row` to `devops_cli_ai_requests_total`, `devops_cli_ai_tokens_total` and `devops_cli_ai_spend_usd_total`. The value SHALL be the row of the `request_scope` context variable, or `other` outside a row. `devops roadmap implement --confirm` SHALL apply its plan in the scope of the row `implement`.

#### Scenario: A request in the stage row
- **WHEN** an agent of `build_agent` sends a request in the scope of the row `stage`
- **THEN** the request, token, spend and answer series of the request have `row` `stage`

#### Scenario: A runner Job
- **WHEN** a runner Job applies the plan of an item
- **THEN** its token and answer series have `row` `implement`
