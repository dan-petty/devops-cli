# ai-model-sampling Specification

## Purpose
Enforces AI model sampling and serving parameter propagation, refusal of unsupported options, and session recording across LLM clients and review pipelines.

## Requirements

### Requirement: Refuse num_ctx on remote providers
The system SHALL raise a configuration error naming the task when its resolved configuration sets `num_ctx` on the `gateway` provider or an OpenAI-compatible provider. The error message SHALL state that the server context comes from the tier's `OLLAMA_CONTEXT_LENGTH` and that `context_window` sizes pages.

#### Scenario: Client rejects num_ctx on gateway
- **WHEN** an LLM client initializes with `num_ctx` configured for provider `gateway`
- **THEN** initialization raises a `ConfigurationError` naming the task and stating that the tier's `OLLAMA_CONTEXT_LENGTH` provides context and `context_window` sizes pages

#### Scenario: Native Ollama client accepts num_ctx
- **WHEN** an LLM client initializes with `num_ctx` configured for provider `ollama`
- **THEN** initialization succeeds and requests transmit `num_ctx` in options

### Requirement: Refuse undeclared AI configuration keys
The system SHALL fail validation when configuration under `ai`, `ai.tasks`, or `ai.tasks.<task>` contains unknown keys. For `top_k`, `min_p`, `presence_penalty`, `repeat_penalty`, `think`, or `keep_alive`, the error SHALL state that the settings belong in a gateway deployment's `litellm_params` or the Ollama tag.

#### Scenario: Undeclared task sampling key fails validation
- **WHEN** configuration data contains `ai.tasks.analysis.top_k`
- **THEN** validation fails naming the key and explaining that it belongs in a gateway deployment's `litellm_params` or the Ollama tag

#### Scenario: Generic undeclared AI key fails validation
- **WHEN** configuration data contains an unknown key under `ai`
- **THEN** validation fails naming the unknown key

### Requirement: Streamed calls preserve sampling and trace headers
The system SHALL send the same sampling options and trace headers on streamed calls as on unstreamed calls across providers.

#### Scenario: Streamed OpenAI-compatible payload carries sampling
- **WHEN** a streamed chat payload is generated for an OpenAI-compatible provider
- **THEN** the payload includes `temperature` and `top_p` matching unstreamed payloads

#### Scenario: Streamed Ollama request carries options and trace headers
- **WHEN** a streamed chat request is dispatched to native Ollama
- **THEN** the request body contains `options` with sampling settings and request headers contain trace context

### Requirement: Model-level sampling option
The system SHALL support a `use_model_sampling` boolean setting in `AIConfig` and `AITaskOverride`. When enabled for a task, requests SHALL omit `temperature` and `top_p` on both gateway and native Ollama paths.

#### Scenario: use_model_sampling omits temperature and top_p
- **WHEN** a task enables or inherits `use_model_sampling`
- **THEN** outbound request payloads for that task carry neither `temperature` nor `top_p`

### Requirement: Review profile sampling recording
The system SHALL record `models` and `sampling` for `analysis`, `verification`, and `compose` tasks in `profile.json`, capturing `temperature`, `top_p`, `max_tokens`, `reasoning_effort`, and `use_model_sampling`. Parameters not sent by the client SHALL be recorded as null.

#### Scenario: Review session records task sampling
- **WHEN** a code review session publishes its profile
- **THEN** `profile.json` contains `models` and `sampling` for analysis, verification, and compose tasks

### Requirement: Reply cache key includes request sampling
The system SHALL include `temperature`, `top_p`, `reasoning_effort`, and reply cap in the options hashed by the response cache key.

#### Scenario: Cache keys partition different temperatures
- **WHEN** two requests with identical messages are dispatched with differing temperatures
- **THEN** each request produces a distinct cache key and dispatches to the model
